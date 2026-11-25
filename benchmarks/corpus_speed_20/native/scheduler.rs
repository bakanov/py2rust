//! Handwritten event calendar with exact phase ordering and reproducible workloads.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    cmp::Reverse,
    collections::{BTreeMap, BinaryHeap, HashSet, VecDeque},
};
const STATUSES: [&str; 7] = [
    "pending", "queued", "running", "on_time", "late", "expired", "rejected",
];
const PENDING: usize = 0;
const QUEUED: usize = 1;
const RUNNING: usize = 2;
const ON_TIME: usize = 3;
const LATE: usize = 4;
const EXPIRED: usize = 5;
const REJECTED: usize = 6;
#[derive(Clone, Serialize)]
struct InputJob {
    id: String,
    arrival: i64,
    service: i64,
    deadline: i64,
}
#[derive(Serialize)]
struct Job {
    #[serde(flatten)]
    input: InputJob,
    status: &'static str,
    started: i64,
    finished: i64,
    worker: i64,
}
#[derive(Serialize)]
struct Event {
    sequence: usize,
    tick: i64,
    job: String,
    status: &'static str,
    worker: i64,
    pending: usize,
    queued: usize,
    running: usize,
    terminal: usize,
}
struct State {
    jobs: Vec<Job>,
    statuses: Vec<usize>,
    trace: Vec<Event>,
    counts: [usize; 7],
    now: i64,
    queue_area: i64,
    busy_area: i64,
    peak_queue: usize,
}
impl State {
    fn transition(&mut self, index: usize, status: usize, worker: usize) {
        self.counts[self.statuses[index]] -= 1;
        self.counts[status] += 1;
        self.statuses[index] = status;
        let job = &mut self.jobs[index];
        job.status = STATUSES[status];
        if status == RUNNING {
            job.started = self.now;
            job.worker = worker as i64;
        } else if status != QUEUED {
            job.finished = self.now;
        }
        let terminal =
            self.statuses.len() - self.counts[PENDING] - self.counts[QUEUED] - self.counts[RUNNING];
        self.trace.push(Event {
            sequence: self.trace.len() + 1,
            tick: self.now,
            job: job.input.id.clone(),
            status: job.status,
            worker: job.worker,
            pending: self.counts[PENDING],
            queued: self.counts[QUEUED],
            running: self.counts[RUNNING],
            terminal,
        });
        self.peak_queue = self.peak_queue.max(self.counts[QUEUED]);
    }
    fn active(&self) -> usize {
        self.counts[PENDING] + self.counts[QUEUED] + self.counts[RUNNING]
    }
}
fn bounded(value: &Value, low: i64, high: i64) -> Result<i64> {
    let value = integer(value)?;
    require(
        (low..=high).contains(&value),
        "integer outside permitted range",
    )?;
    Ok(value)
}
fn interval(value: &Value, low: i64, high: i64) -> Result<(i64, i64)> {
    let pair = value.as_array().ok_or("expected interval array")?;
    require(pair.len() == 2, "expected lower and upper bound")?;
    let low = bounded(&pair[0], low, high)?;
    Ok((low, bounded(&pair[1], low, high)?))
}
fn resolve(workload: &Value) -> Result<(Vec<InputJob>, Value)> {
    let mode = string(&workload["mode"])?;
    if mode == "explicit" {
        exact(workload, &["mode", "jobs"])?;
        let raw = workload["jobs"].as_array().ok_or("expected jobs array")?;
        require(raw.len() <= 512, "at most 512 jobs")?;
        let mut seen = HashSet::new();
        let mut jobs = Vec::with_capacity(raw.len());
        for row in raw {
            exact(row, &["id", "arrival", "service", "deadline"])?;
            let id = string(&row["id"])?;
            require(
                rt::regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", id)? && seen.insert(id),
                "invalid/duplicate ID",
            )?;
            let arrival = bounded(&row["arrival"], 0, 1000000000)?;
            jobs.push(InputJob {
                id: id.into(),
                arrival,
                service: bounded(&row["service"], 1, 1000000)?,
                deadline: bounded(&row["deadline"], arrival, 2000000000)?,
            });
        }
        return Ok((
            jobs,
            json!({"algorithm":"none","seed":0,"state":0,"draws":0}),
        ));
    }
    require(mode == "generated", "unknown workload mode")?;
    exact(
        workload,
        &["mode", "seed", "count", "gap", "service", "slack"],
    )?;
    let seed = bounded(&workload["seed"], 1, 2147483646)?;
    let count = bounded(&workload["count"], 0, 512)?;
    let ranges = [
        interval(&workload["gap"], 0, 1000000)?,
        interval(&workload["service"], 1, 1000000)?,
        interval(&workload["slack"], 0, 1000000)?,
    ];
    let (mut state, mut draws, mut arrival) = (seed, 0, 0);
    let mut jobs = Vec::with_capacity(count as usize);
    for index in 0..count {
        let mut values = [0; 3];
        for (slot, &(low, high)) in ranges.iter().enumerate() {
            let width = high - low + 1;
            let limit = 2147483646 / width * width;
            loop {
                require(draws < 65536, "generator draw limit reached")?;
                state = 16807 * state % 2147483647;
                draws += 1;
                let value = state - 1;
                if value < limit {
                    values[slot] = low + value % width;
                    break;
                }
            }
        }
        arrival += values[0];
        jobs.push(InputJob {
            id: format!("job_{}", index + 1),
            arrival,
            service: values[1],
            deadline: arrival + values[2],
        });
    }
    Ok((
        jobs,
        json!({"algorithm":"park-miller-16807-v1","seed":seed,"state":state,"draws":draws}),
    ))
}
fn simulate(jobs: &[InputJob], workers: usize, capacity: usize) -> Result<State> {
    let mut state = State {
        jobs: jobs
            .iter()
            .map(|job| Job {
                input: job.clone(),
                status: "pending",
                started: -1,
                finished: -1,
                worker: -1,
            })
            .collect(),
        statuses: vec![PENDING; jobs.len()],
        trace: Vec::new(),
        counts: [0; 7],
        now: 0,
        queue_area: 0,
        busy_area: 0,
        peak_queue: 0,
    };
    state.counts[PENDING] = jobs.len();
    let mut owners = vec![None; workers];
    let mut queue = VecDeque::new();
    let mut calendar = BinaryHeap::new();
    for (i, job) in jobs.iter().enumerate() {
        calendar.push(Reverse((job.arrival, 3, i)));
        calendar.push(Reverse((job.deadline, 1, i)));
    }
    while state.active() > 0 {
        let now = calendar.peek().ok_or("empty active calendar")?.0 .0;
        state.queue_area += (now - state.now) * state.counts[QUEUED] as i64;
        state.busy_area += (now - state.now) * state.counts[RUNNING] as i64;
        state.now = now;
        calendar.push(Reverse((now, 2, 0)));
        while calendar.peek().is_some_and(|e| e.0 .0 == now) {
            let Reverse((_, phase, index)) = calendar.pop().unwrap();
            if phase == 2 {
                while let Some(worker) = owners.iter().position(Option::is_none) {
                    let Some(index) = queue.pop_front() else {
                        break;
                    };
                    owners[worker] = Some(index);
                    state.transition(index, RUNNING, worker);
                    calendar.push(Reverse((now + jobs[index].service, 0, index)));
                }
            } else if phase == 0 {
                require(state.statuses[index] == RUNNING, "unexpected completion")?;
                owners[state.jobs[index].worker as usize] = None;
                state.transition(
                    index,
                    if now <= jobs[index].deadline {
                        ON_TIME
                    } else {
                        LATE
                    },
                    0,
                );
            } else if phase == 1 && state.statuses[index] == QUEUED {
                if let Some(position) = queue.iter().position(|entry| *entry == index) {
                    queue.remove(position);
                }
                state.transition(index, EXPIRED, 0);
            } else if phase == 3 {
                let worker = owners.iter().position(Option::is_none);
                if now == jobs[index].deadline {
                    state.transition(index, EXPIRED, 0);
                } else if let Some(worker) = worker {
                    owners[worker] = Some(index);
                    state.transition(index, RUNNING, worker);
                    calendar.push(Reverse((now + jobs[index].service, 0, index)));
                } else if queue.len() < capacity {
                    queue.push_back(index);
                    state.transition(index, QUEUED, 0);
                } else {
                    state.transition(index, REJECTED, 0);
                }
            }
        }
        require(
            queue.len() == state.counts[QUEUED] && queue.len() <= capacity,
            "queue conservation failed",
        )?;
        require(state.counts[RUNNING] <= workers, "worker capacity exceeded")?;
    }
    Ok(state)
}
fn summarize(state: &State, workers: usize, generator: Value) -> Result<Value> {
    let (mut waiting, mut response, mut completed_wait) = (0, 0, 0);
    for job in &state.jobs {
        let arrival = job.input.arrival;
        if job.started >= 0 {
            completed_wait += job.started - arrival;
            response += job.finished - arrival;
        }
        waiting += if job.started >= 0 {
            job.started
        } else {
            job.finished
        } - arrival;
    }
    require(
        waiting == state.queue_area,
        "queue time integral disagrees with outcomes",
    )?;
    let completed = state.counts[ON_TIME] + state.counts[LATE];
    let counts: BTreeMap<_, _> = STATUSES.into_iter().zip(state.counts).collect();
    Ok(
        json!({"version":1,"generator":generator,"jobs":state.jobs.len(),"counts":counts,"horizon_ticks":state.now,"peak_queue":state.peak_queue,"trace_records":state.trace.len(),"queue_ticks":state.queue_area,"busy_ticks":state.busy_area,"utilization":{"numerator":state.busy_area,"denominator":workers as i64*state.now},"mean_queue":{"numerator":state.queue_area,"denominator":state.now},"mean_completed_wait":{"numerator":completed_wait,"denominator":completed},"mean_completed_response":{"numerator":response,"denominator":completed}}),
    )
}
fn render(
    config: &Value,
    jobs: &[InputJob],
    state: &State,
    summary: &Value,
) -> Result<BTreeMap<String, Vec<u8>>> {
    let mut trace = Vec::new();
    for event in &state.trace {
        trace.extend(canonical(&serde_json::to_value(event)?)?);
    }
    let mut text = vec![
        "Discrete-event scheduler".into(),
        format!("Counts: {}", rt::json_canonical_view(&summary["counts"])?),
        format!("Horizon: {} ticks", state.now),
        format!("Statistics: {}", rt::json_canonical_view(summary)?),
    ];
    for job in &state.jobs {
        text.push(format!(
            "{}: {} start={} finish={}",
            job.input.id, job.status, job.started, job.finished
        ));
    }
    let mut replay = config.clone();
    replay["output"] = json!("replayed");
    let explicit = json!({"version":1,"workers":config["workers"],"queue_capacity":config["queue_capacity"],"workload":{"mode":"explicit","jobs":jobs},"output":"replayed"});
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::from([
        ("summary.json".into(), canonical(summary)?),
        (
            "jobs.json".into(),
            canonical(&serde_json::to_value(&state.jobs)?)?,
        ),
        ("trace.jsonl".into(), trace),
        ("report.txt".into(), (text.join("\n") + "\n").into_bytes()),
        ("scheduler-job.json".into(), canonical(&replay)?),
        ("resolved-job.json".into(), canonical(&explicit)?),
    ]);
    require(
        files.values().map(Vec::len).sum::<usize>() <= 4194304,
        "report bundle exceeds 4 MiB",
    )?;
    let manifest: BTreeMap<_, _> = files
        .iter()
        .map(|(name, data)| {
            (
                name.clone(),
                json!({"bytes":data.len(),"sha256":digest(data)}),
            )
        })
        .collect();
    files.insert(
        "manifest.json".into(),
        canonical(&json!({"version":1,"files":manifest}))?,
    );
    Ok(files)
}
fn run() -> Result<()> {
    let document = Document::read(
        absolute(
            &std::env::var("SCHEDULER_CONFIG").unwrap_or_else(|_| "scheduler-job.json".into()),
            &std::env::current_dir()?,
        )?,
        262144,
    )?;
    let config = rt::json_loads(std::str::from_utf8(&document.data)?)?;
    exact(
        &config,
        &["version", "workers", "queue_capacity", "workload", "output"],
    )?;
    require(integer(&config["version"])? == 1, "unsupported version")?;
    let workers = bounded(&config["workers"], 1, 32)? as usize;
    let capacity = bounded(&config["queue_capacity"], 0, 512)? as usize;
    let output = absolute(
        string(&config["output"])?,
        document.path.parent().ok_or("missing parent")?,
    )?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let (jobs, generator) = resolve(&config["workload"])?;
    let state = simulate(&jobs, workers, capacity)?;
    let summary = summarize(&state, workers, generator)?;
    publish_exact(
        &output,
        render(&config, &jobs, &state, &summary)?,
        &[document],
        "scheduler",
    )?;
    print!("{}", std::str::from_utf8(&canonical(&summary)?)?);
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
