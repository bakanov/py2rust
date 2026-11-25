//! Handwritten warehouse simulation with compact undo records and complete replay exports.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Clone, Copy, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
enum Command {
    Up,
    Down,
    Left,
    Right,
    Undo,
}
impl Command {
    fn parse(value: &str) -> Result<Self> {
        Ok(match value {
            "up" => Self::Up,
            "down" => Self::Down,
            "left" => Self::Left,
            "right" => Self::Right,
            "undo" => Self::Undo,
            _ => return Err("unknown command".into()),
        })
    }
    fn offset(self) -> (isize, isize) {
        match self {
            Self::Up => (-1, 0),
            Self::Down => (1, 0),
            Self::Left => (0, -1),
            Self::Right => (0, 1),
            Self::Undo => unreachable!(),
        }
    }
}
struct Program {
    title: String,
    grid: Vec<Vec<u8>>,
    robot: [usize; 2],
    commands: Vec<Command>,
}
fn display(title: &str) -> Result<String> {
    Ok(rt::str_split_whitespace(&rt::unicode_normalize("NFKC", title)?).join(" "))
}
fn parse(source: &Value) -> Result<Program> {
    exact(source, &["version", "title", "grid", "commands"])?;
    require(
        integer(&source["version"])? == 1,
        "unsupported source version",
    )?;
    let title = string(&source["title"])?;
    let shown = display(title)?;
    require(
        (1..=100).contains(&title.chars().count()) && (1..=100).contains(&shown.chars().count()),
        "title character limit",
    )?;
    require(
        shown
            .chars()
            .all(|c| c >= ' ' && !('\u{7f}'..='\u{9f}').contains(&c)),
        "control character in title",
    )?;
    let rows = source["grid"].as_array().ok_or("expected grid array")?;
    require((1..=32).contains(&rows.len()), "grid row limit")?;
    let width = string(&rows[0])?.chars().count();
    require((1..=32).contains(&width), "grid width limit")?;
    let (mut robots, mut boxes) = (0, 0);
    let mut robot = [0, 0];
    let mut grid = Vec::with_capacity(rows.len());
    for (r, row) in rows.iter().enumerate() {
        let line = string(row)?;
        require(line.chars().count() == width, "ragged grid")?;
        require(
            line.bytes().all(|c| matches!(c, b'#' | b'.' | b'@' | b'$')),
            "unknown grid cell",
        )?;
        for (c, cell) in line.bytes().enumerate() {
            if cell == b'@' {
                robots += 1;
                robot = [r, c];
            }
            if cell == b'$' {
                boxes += 1;
            }
        }
        grid.push(line.as_bytes().to_vec());
    }
    require(robots == 1, "grid requires exactly one robot")?;
    require(boxes <= 64, "box count limit")?;
    let raw = source["commands"]
        .as_array()
        .ok_or("expected commands array")?;
    require(raw.len() <= 2048, "command count limit")?;
    let commands = raw
        .iter()
        .map(|v| Command::parse(string(v)?))
        .collect::<Result<Vec<_>>>()?;
    Ok(Program {
        title: title.into(),
        grid,
        robot,
        commands,
    })
}
#[derive(Serialize)]
struct State {
    grid: Vec<String>,
    robot: [usize; 2],
    boxes: Vec<[usize; 2]>,
    history_depth: usize,
}
fn state(grid: &[Vec<u8>], robot: [usize; 2], history_depth: usize) -> State {
    let mut boxes = Vec::new();
    for (r, row) in grid.iter().enumerate() {
        for (c, cell) in row.iter().enumerate() {
            if *cell == b'$' {
                boxes.push([r, c]);
            }
        }
    }
    State {
        grid: grid
            .iter()
            .map(|row| String::from_utf8(row.clone()).unwrap())
            .collect(),
        robot,
        boxes,
        history_depth,
    }
}
struct Move {
    command: Command,
    old: [usize; 2],
    new: [usize; 2],
    box_at: Option<[usize; 2]>,
}
#[derive(Serialize)]
struct Step {
    index: usize,
    command: Command,
    action: &'static str,
    reason: &'static str,
    state: State,
}
#[derive(Serialize)]
struct Summary {
    commands: usize,
    walks: usize,
    pushes: usize,
    undos: usize,
    blocked: usize,
    history_depth: usize,
}
#[derive(Serialize)]
struct Simulation {
    title: String,
    initial: State,
    #[serde(rename = "final")]
    final_state: State,
    summary: Summary,
    active_commands: Vec<Command>,
    trace: Vec<Step>,
}
fn inside(grid: &[Vec<u8>], r: isize, c: isize) -> bool {
    r >= 0 && c >= 0 && (r as usize) < grid.len() && (c as usize) < grid[0].len()
}
fn blocked(grid: &[Vec<u8>], r: isize, c: isize, dr: isize, dc: isize) -> &'static str {
    if !inside(grid, r, c) {
        return "boundary";
    }
    match grid[r as usize][c as usize] {
        b'#' => "wall",
        b'$' => {
            if !inside(grid, r + dr, c + dc) {
                "box_boundary"
            } else {
                match grid[(r + dr) as usize][(c + dc) as usize] {
                    b'#' => "box_wall",
                    b'$' => "box_chain",
                    _ => "",
                }
            }
        }
        _ => "",
    }
}
fn simulate(program: Program) -> Result<Simulation> {
    let mut grid = program.grid;
    let mut robot = program.robot;
    let initial = state(&grid, robot, 0);
    let mut history: Vec<Move> = Vec::new();
    let mut trace = Vec::with_capacity(program.commands.len());
    let mut summary = Summary {
        commands: program.commands.len(),
        walks: 0,
        pushes: 0,
        undos: 0,
        blocked: 0,
        history_depth: 0,
    };
    for (index, &command) in program.commands.iter().enumerate() {
        let mut action = "blocked";
        let reason;
        if command == Command::Undo {
            if let Some(previous) = history.pop() {
                grid[previous.new[0]][previous.new[1]] = b'.';
                if let Some(box_at) = previous.box_at {
                    grid[box_at[0]][box_at[1]] = b'.';
                    grid[previous.new[0]][previous.new[1]] = b'$';
                }
                robot = previous.old;
                grid[robot[0]][robot[1]] = b'@';
                action = if previous.box_at.is_some() {
                    "undo_push"
                } else {
                    "undo_move"
                };
                summary.undos += 1;
                reason = "";
            } else {
                reason = "empty_history";
            }
        } else {
            let (dr, dc) = command.offset();
            let (r, c) = (robot[0] as isize + dr, robot[1] as isize + dc);
            reason = blocked(&grid, r, c, dr, dc);
            if reason.is_empty() {
                require(history.len() < 1024, "undo history limit")?;
                let new = [r as usize, c as usize];
                let box_at = (grid[new[0]][new[1]] == b'$')
                    .then_some([(r + dr) as usize, (c + dc) as usize]);
                history.push(Move {
                    command,
                    old: robot,
                    new,
                    box_at,
                });
                grid[robot[0]][robot[1]] = b'.';
                grid[new[0]][new[1]] = b'@';
                if let Some(box_at) = box_at {
                    grid[box_at[0]][box_at[1]] = b'$';
                    summary.pushes += 1;
                    action = "push";
                } else {
                    summary.walks += 1;
                    action = "move";
                }
                robot = new;
            }
        }
        if action == "blocked" {
            summary.blocked += 1;
        }
        trace.push(Step {
            index,
            command,
            action,
            reason,
            state: state(&grid, robot, history.len()),
        });
    }
    summary.history_depth = history.len();
    let final_state = state(&grid, robot, history.len());
    let active_commands = history.into_iter().map(|m| m.command).collect();
    Ok(Simulation {
        title: program.title,
        initial,
        final_state,
        summary,
        active_commands,
        trace,
    })
}
fn program(title: &Value, grid: &Value, commands: &[Command]) -> Result<Vec<u8>> {
    let value = json!({"version":1,"title":title,"grid":grid,"commands":commands});
    parse(&value)?;
    canonical(&value)
}
fn request(mode: &str, input: &str, output: &str) -> Result<Vec<u8>> {
    canonical(&json!({"version":1,"mode":mode,"input":input,"output":output}))
}
fn bundle(mode: &str, source: &Value, results: &Simulation) -> Result<BTreeMap<String, Vec<u8>>> {
    let archive = canonical(&json!({"version":1,"source":source,"results":results}))?;
    let mut rewind = results.active_commands.clone();
    rewind.extend(std::iter::repeat(Command::Undo).take(results.active_commands.len()));
    let summary = serde_json::to_value(&results.summary)?;
    let mut lines = vec![
        display(string(&source["title"])?)?,
        rt::json_canonical_view(&summary)?,
        String::new(),
    ];
    lines.extend(results.final_state.grid.iter().cloned());
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::from([
        (
            "report.json".into(),
            canonical(
                &json!({"version":1,"mode":mode,"summary":summary,"archive_sha256":digest(&archive)}),
            )?,
        ),
        ("archive.json".into(), archive),
        ("program.json".into(), canonical(source)?),
        (
            "trace.json".into(),
            canonical(&serde_json::to_value(&results.trace)?)?,
        ),
        (
            "continuation.json".into(),
            program(&source["title"], &source["grid"], &results.active_commands)?,
        ),
        (
            "rewind.json".into(),
            program(&source["title"], &source["grid"], &rewind)?,
        ),
        (
            "layout.json".into(),
            program(
                &source["title"],
                &serde_json::to_value(&results.final_state.grid)?,
                &[],
            )?,
        ),
        ("layout.txt".into(), (lines.join("\n") + "\n").into_bytes()),
        (
            "replay.json".into(),
            request("verify", "archive.json", "replayed")?,
        ),
        (
            "simulate.json".into(),
            request("simulate", "program.json", "simulated")?,
        ),
        (
            "continue-job.json".into(),
            request("simulate", "continuation.json", "continued")?,
        ),
        (
            "rewind-job.json".into(),
            request("simulate", "rewind.json", "rewound")?,
        ),
        (
            "restart-job.json".into(),
            request("simulate", "layout.json", "restarted")?,
        ),
    ]);
    require(
        files.values().all(|data| data.len() <= 16777216),
        "export byte limit",
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
        canonical(&serde_json::to_value(manifest)?)?,
    );
    Ok(files)
}
fn run() -> Result<()> {
    let request = Document::read(
        absolute(
            &std::env::var("WAREHOUSE_CONFIG").unwrap_or_else(|_| "warehouse-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = request.json()?;
    exact(&config, &["version", "mode", "input", "output"])?;
    require(
        integer(&config["version"])? == 1,
        "unsupported request version",
    )?;
    let mode = string(&config["mode"])?;
    require(matches!(mode, "simulate" | "verify"), "unknown mode")?;
    let base = request.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output already exists",
    )?;
    let document = Document::read(
        absolute(string(&config["input"])?, base)?,
        if mode == "verify" { 16777216 } else { 2097152 },
    )?;
    let data = document.json()?;
    let source = if mode == "verify" {
        exact(&data, &["version", "source", "results"])?;
        require(
            integer(&data["version"])? == 1,
            "unsupported archive version",
        )?;
        &data["source"]
    } else {
        &data
    };
    let results = simulate(parse(source)?)?;
    if mode == "verify" {
        require(
            canonical(&data["results"])? == canonical(&serde_json::to_value(&results)?)?,
            "archive results do not match recomputed warehouse trace",
        )?;
    }
    publish_exact(
        &output,
        bundle(mode, source, &results)?,
        &[request, document],
        "warehouse",
    )?;
    print!(
        "{}",
        std::str::from_utf8(&canonical(&serde_json::to_value(results.summary)?)?)?
    );
    Ok(())
}
fn main() {
    if let Err(error) = run() {
        eprintln!("{error}");
        std::process::exit(2);
    }
}
