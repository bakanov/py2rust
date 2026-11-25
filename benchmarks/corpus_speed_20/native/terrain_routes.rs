//! Handwritten stable A* and complete terrain-route exports.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Serialize;
use serde_json::{json, Value};
use std::{
    cmp::Reverse,
    collections::{BTreeMap, BinaryHeap, HashSet},
    path::PathBuf,
};

struct Grid {
    rows: Vec<String>,
    cells: Vec<i64>,
    width: usize,
    minimum: i64,
    passable: usize,
}
#[derive(Serialize)]
struct Query {
    id: String,
    start: [usize; 2],
    goal: [usize; 2],
}
#[derive(Default, Serialize)]
struct Stats {
    pushed: usize,
    popped: usize,
    expanded: usize,
    stale: usize,
    discovered: usize,
    frontier_peak: usize,
    frontier_remaining: usize,
}
#[derive(Serialize)]
struct Route<'a> {
    id: &'a str,
    start: [usize; 2],
    goal: [usize; 2],
    status: &'static str,
    blocked: Vec<&'static str>,
    cost: Option<i64>,
    steps: usize,
    path: Vec<[usize; 2]>,
    stats: Stats,
}
fn read(path: PathBuf, limit: usize) -> Result<Document> {
    Document::read(path, limit).map_err(|error| format!("reading regular file: {error}").into())
}
fn parsed(document: &Document) -> Result<Value> {
    rt::json_loads(std::str::from_utf8(&document.data)?)
}
fn terrain(value: &Value) -> Result<BTreeMap<String, i64>> {
    exact(value, &["version", "costs"])?;
    require(
        integer(&value["version"])? == 1,
        "unsupported terrain version",
    )?;
    let values = value["costs"]
        .as_object()
        .ok_or("expected terrain costs object")?;
    require(values.len() <= 16, "terrain count exceeds 16")?;
    let mut costs = BTreeMap::new();
    for (symbol, value) in values {
        require(
            symbol.len() == 1
                && symbol.as_bytes()[0] >= b' '
                && symbol.as_bytes()[0] <= b'~'
                && !"#SG*@X".contains(symbol),
            "invalid terrain symbol",
        )?;
        let cost = integer(value)?;
        require(
            (0..=1000000000).contains(&cost),
            "terrain cost outside bounds",
        )?;
        costs.insert(symbol.clone(), cost);
    }
    Ok(costs)
}
fn load(text: &str, costs: &BTreeMap<String, i64>) -> Result<Grid> {
    let normalized = text.replace("\r\n", "\n");
    require(!normalized.contains('\r'), "bare carriage return in grid")?;
    let mut rows: Vec<String> = normalized.split('\n').map(str::to_owned).collect();
    if rows.last().is_some_and(String::is_empty) {
        rows.pop();
    }
    require((1..=64).contains(&rows.len()), "grid height must be 1..64")?;
    let width = rows[0].chars().count();
    require((1..=64).contains(&width), "grid width must be 1..64")?;
    let mut cells = Vec::with_capacity(width * rows.len());
    let (mut minimum, mut passable) = (1000000000, 0);
    for row in &rows {
        require(row.chars().count() == width, "grid is not rectangular")?;
        for ch in row.chars() {
            let cost = if ch == '#' {
                -1
            } else {
                *costs.get(&ch.to_string()).ok_or("unknown grid terrain")?
            };
            if cost >= 0 {
                minimum = minimum.min(cost);
                passable += 1;
            }
            cells.push(cost);
        }
    }
    Ok(Grid {
        rows,
        cells,
        width,
        minimum: if passable > 0 { minimum } else { 0 },
        passable,
    })
}
fn coordinate(grid: &Grid, value: &Value) -> Result<[usize; 2]> {
    let values = value.as_array().ok_or("coordinates must be an array")?;
    require(values.len() == 2, "coordinates must be [row, column]")?;
    let (row, column) = (integer(&values[0])?, integer(&values[1])?);
    require(
        row >= 0 && row < (grid.rows.len() as i64) && column >= 0 && column < (grid.width as i64),
        "coordinate outside grid",
    )?;
    Ok([row as usize, column as usize])
}
fn requests(grid: &Grid, value: &Value) -> Result<Vec<Query>> {
    let rows = value.as_array().ok_or("expected request array")?;
    require(rows.len() <= 64, "query count exceeds 64")?;
    let mut seen = HashSet::new();
    rows.iter()
        .map(|row| {
            exact(row, &["id", "start", "goal"])?;
            let id = string(&row["id"])?;
            require(
                (1..=64).contains(&id.chars().count()) && id.len() <= 256 && !id.contains('\0'),
                "invalid query id",
            )?;
            require(seen.insert(id), "duplicate query id")?;
            Ok(Query {
                id: id.into(),
                start: coordinate(grid, &row["start"])?,
                goal: coordinate(grid, &row["goal"])?,
            })
        })
        .collect()
}
fn estimate(position: usize, goal: usize, grid: &Grid) -> i64 {
    ((position / grid.width).abs_diff(goal / grid.width)
        + (position % grid.width).abs_diff(goal % grid.width)) as i64
        * grid.minimum
}
fn solve<'a>(grid: &Grid, query: &'a Query) -> Result<Route<'a>> {
    let start = query.start[0] * grid.width + query.start[1];
    let goal = query.goal[0] * grid.width + query.goal[1];
    let mut result = Route {
        id: &query.id,
        start: query.start,
        goal: query.goal,
        status: "blocked",
        blocked: Vec::new(),
        cost: None,
        steps: 0,
        path: Vec::new(),
        stats: Stats::default(),
    };
    if grid.cells[start] < 0 {
        result.blocked.push("start");
    }
    if grid.cells[goal] < 0 {
        result.blocked.push("goal");
    }
    if !result.blocked.is_empty() {
        return Ok(result);
    }
    let mut distances = vec![-1; grid.cells.len()];
    let mut parents = vec![None; grid.cells.len()];
    let mut closed = vec![false; grid.cells.len()];
    let mut heap = BinaryHeap::new();
    distances[start] = 0;
    heap.push(Reverse((estimate(start, goal, grid), 0, start)));
    let stats = &mut result.stats;
    stats.pushed = 1;
    stats.discovered = 1;
    stats.frontier_peak = 1;
    while let Some(Reverse((_, distance, position))) = heap.pop() {
        stats.popped += 1;
        if closed[position] || distance != distances[position] {
            stats.stale += 1;
            continue;
        }
        closed[position] = true;
        stats.expanded += 1;
        if position == goal {
            break;
        }
        let (r, c) = (
            (position / grid.width) as isize,
            (position % grid.width) as isize,
        );
        for (dr, dc) in [(-1, 0), (0, -1), (0, 1), (1, 0)] {
            let (row, column) = (r + dr, c + dc);
            if row < 0
                || row >= grid.rows.len() as isize
                || column < 0
                || column >= grid.width as isize
            {
                continue;
            }
            let following = row as usize * grid.width + column as usize;
            if grid.cells[following] < 0 || closed[following] {
                continue;
            }
            let cost = distance + grid.cells[following];
            if distances[following] < 0 || cost < distances[following] {
                if distances[following] < 0 {
                    stats.discovered += 1;
                }
                distances[following] = cost;
                parents[following] = Some(position);
                heap.push(Reverse((
                    cost + estimate(following, goal, grid),
                    cost,
                    following,
                )));
                stats.pushed += 1;
                stats.frontier_peak = stats.frontier_peak.max(heap.len());
            }
        }
    }
    stats.frontier_remaining = heap.len();
    result.status = "unreachable";
    if closed[goal] {
        let mut positions = vec![goal];
        let mut current = goal;
        while current != start {
            current = parents[current].ok_or("invalid route predecessor chain")?;
            require(
                positions.len() < grid.cells.len(),
                "invalid route predecessor chain",
            )?;
            positions.push(current);
        }
        result.path = positions
            .into_iter()
            .rev()
            .map(|p| [p / grid.width, p % grid.width])
            .collect();
        result.status = "found";
        result.cost = Some(distances[goal]);
        result.steps = result.path.len() - 1;
    }
    Ok(result)
}
fn render(grid: &Grid, route: &Route) -> Result<String> {
    let mut marked = vec![false; grid.cells.len()];
    for point in &route.path {
        marked[point[0] * grid.width + point[1]] = true;
    }
    let start = route.start[0] * grid.width + route.start[1];
    let goal = route.goal[0] * grid.width + route.goal[1];
    let mut text = format!(
        "Route {}: {} cost={}\n",
        rt::json_canonical_view(&json!(route.id))?,
        route.status,
        rt::json_canonical_view(&json!(route.cost))?
    );
    for (r, row) in grid.rows.iter().enumerate() {
        for (c, original) in row.bytes().enumerate() {
            let p = r * grid.width + c;
            let symbol = if p == start || p == goal {
                if grid.cells[p] < 0 {
                    b'X'
                } else if start == goal {
                    b'@'
                } else if p == start {
                    b'S'
                } else {
                    b'G'
                }
            } else if marked[p] {
                b'*'
            } else {
                original
            };
            text.push(symbol as char);
        }
        text.push('\n');
    }
    Ok(text)
}
fn run() -> Result<i32> {
    let mode = std::env::var("TERRAIN_MODE").unwrap_or_else(|_| "preview".into());
    require(
        matches!(mode.as_str(), "preview" | "write"),
        "invalid terrain mode",
    )?;
    let configuration = read(
        absolute(
            &std::env::var("TERRAIN_CONFIG").unwrap_or_else(|_| "terrain-job.json".into()),
            &std::env::current_dir()?,
        )?,
        65536,
    )?;
    let config = parsed(&configuration)?;
    exact(&config, &["grid", "terrain", "requests", "output"])?;
    let base = configuration.path.parent().ok_or("missing parent")?;
    let output = absolute(string(&config["output"])?, base)?;
    require(
        !output.exists() && !output.is_symlink(),
        "output directory already exists",
    )?;
    let source = read(absolute(string(&config["grid"])?, base)?, 8192)?;
    let rules = read(absolute(string(&config["terrain"])?, base)?, 65536)?;
    let queries = read(absolute(string(&config["requests"])?, base)?, 1048576)?;
    let costs = terrain(&parsed(&rules)?)?;
    let grid = load(std::str::from_utf8(&source.data)?, &costs)?;
    let wanted = requests(&grid, &parsed(&queries)?)?;
    let mut results = Vec::with_capacity(wanted.len());
    let mut pictures =
        vec!["S=start G=goal @=start-and-goal *=path X=blocked-endpoint #=wall\n".to_string()];
    let mut paths = Vec::new();
    let mut counts = BTreeMap::from([("found", 0), ("unreachable", 0), ("blocked", 0)]);
    for query in &wanted {
        let route = solve(&grid, query)?;
        *counts.get_mut(route.status).unwrap() += 1;
        pictures.push(render(&grid, &route)?);
        paths.extend(canonical(&serde_json::to_value(&route)?)?);
        results.push(route);
    }
    let mut files: BTreeMap<String, Vec<u8>> = BTreeMap::from([
        (
            "grid.txt".into(),
            (grid.rows.join("\n") + "\n").into_bytes(),
        ),
        (
            "terrain.json".into(),
            canonical(&json!({"version":1,"costs":costs}))?,
        ),
        (
            "requests.json".into(),
            canonical(&serde_json::to_value(&wanted)?)?,
        ),
    ]);
    let hashes: BTreeMap<_, _> = files
        .iter()
        .map(|(name, data)| (name.clone(), digest(data)))
        .collect();
    let report = json!({"version":1,"grid":{"width":grid.width,"height":grid.rows.len(),"passable":grid.passable,"minimum_cost":grid.minimum},"input_sha256":hashes,"queries":wanted.len(),"counts":counts,"routes":results});
    files.insert("routes.json".into(), canonical(&report)?);
    files.insert("paths.jsonl".into(), paths);
    files.insert("routes.txt".into(), pictures.join("\n").into_bytes());
    require(
        files.values().all(|v| v.len() <= 16777216),
        "output file exceeds 16 MiB",
    )?;
    let checksums: BTreeMap<_, _> = files
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
        (rt::pretty(&json!({"version":1,"files":checksums}))? + "\n").into_bytes(),
    );
    let documents = [configuration, source, rules, queries];
    for doc in &documents {
        doc.unchanged()?;
    }
    if mode == "write" {
        publish_exact(&output, files, &documents, "terrain")?;
    }
    print!("{}", std::str::from_utf8(&canonical(&report)?)?);
    Ok(i32::from(counts["blocked"] + counts["unreachable"] > 0))
}
fn main() {
    match run() {
        Ok(status) => std::process::exit(status),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(2);
        }
    }
}
