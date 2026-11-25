//! Handwritten Bellman–Ford with stable edge order and complete route/cycle witnesses.
mod common;
use common::*;
use py2rust_service_runtime as rt;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};

#[derive(Deserialize)]
struct RawEdge {
    id: String,
    #[serde(rename = "from")]
    source: String,
    #[serde(rename = "to")]
    target: String,
    cost: i64,
}
#[derive(Deserialize)]
struct Query {
    #[serde(rename = "from")]
    source: String,
    #[serde(rename = "to")]
    target: String,
    #[serde(default)]
    closed_nodes: Vec<String>,
    #[serde(default)]
    closed_edges: Vec<String>,
}
#[derive(Deserialize)]
struct Input {
    nodes: Vec<String>,
    edges: Vec<RawEdge>,
    queries: Vec<Query>,
}
struct Edge {
    id: String,
    source: usize,
    target: usize,
    cost: i64,
}
struct Graph {
    nodes: Vec<String>,
    indices: HashMap<String, usize>,
    edges: Vec<Edge>,
    edge_ids: HashSet<String>,
}
impl Graph {
    fn new(nodes: Vec<String>, raw: Vec<RawEdge>) -> Result<Self> {
        require(
            (1..=100).contains(&nodes.len()),
            "expected 1–100 graph nodes",
        )?;
        let mut indices = HashMap::new();
        for (i, name) in nodes.iter().enumerate() {
            require(
                (1..=128).contains(&name.chars().count()),
                "invalid node name",
            )?;
            require(
                indices.insert(name.clone(), i).is_none(),
                "duplicate graph node",
            )?;
        }
        require(raw.len() <= 2000, "graph exceeds 2000 edges")?;
        let mut edge_ids = HashSet::new();
        let mut edges = Vec::with_capacity(raw.len());
        for edge in raw {
            require(
                !edge.id.is_empty() && edge_ids.insert(edge.id.clone()),
                "edge IDs must be unique",
            )?;
            let source = *indices
                .get(&edge.source)
                .ok_or("edge references an unknown node")?;
            let target = *indices
                .get(&edge.target)
                .ok_or("edge references an unknown node")?;
            require(
                (-1000000000..=1000000000).contains(&edge.cost),
                "edge cost exceeds supported bound",
            )?;
            edges.push(Edge {
                id: edge.id,
                source,
                target,
                cost: edge.cost,
            });
        }
        Ok(Self {
            nodes,
            indices,
            edges,
            edge_ids,
        })
    }
    fn solve(&self, query: &Query) -> Result<Value> {
        let start = *self
            .indices
            .get(&query.source)
            .ok_or("unknown query endpoint")?;
        let destination = *self
            .indices
            .get(&query.target)
            .ok_or("unknown query endpoint")?;
        let n = self.nodes.len();
        let mut closed = vec![false; n];
        for name in &query.closed_nodes {
            closed[*self.indices.get(name).ok_or("unknown closed node")?] = true;
        }
        let mut closed_edges = HashSet::new();
        for id in &query.closed_edges {
            require(self.edge_ids.contains(id), "unknown closed edge")?;
            closed_edges.insert(id.as_str());
        }
        if closed[start] || closed[destination] {
            return Ok(json!({"status":"closed","from":query.source,"to":query.target}));
        }
        let edges: Vec<_> = self
            .edges
            .iter()
            .filter(|edge| {
                !closed[edge.source]
                    && !closed[edge.target]
                    && !closed_edges.contains(edge.id.as_str())
            })
            .collect();
        let mut distances: Vec<Option<i64>> = vec![None; n];
        let mut parents: Vec<Option<&Edge>> = vec![None; n];
        let mut changed = Vec::new();
        let (mut passes, mut relaxations) = (0, 0);
        distances[start] = Some(0);
        for _ in 0..n {
            changed.clear();
            passes += 1;
            for &edge in &edges {
                if let Some(previous) = distances[edge.source] {
                    let cost = previous + edge.cost;
                    if distances[edge.target].map_or(true, |old| cost < old) {
                        distances[edge.target] = Some(cost);
                        parents[edge.target] = Some(edge);
                        changed.push(edge.target);
                        relaxations += 1;
                    }
                }
            }
            if changed.is_empty() {
                break;
            }
        }
        let mut relevant = vec![false; n];
        relevant[destination] = true;
        for _ in 0..n {
            for edge in &edges {
                if relevant[edge.target] {
                    relevant[edge.source] = true;
                }
            }
        }
        for seed in changed {
            if relevant[seed] {
                let mut current = seed;
                for _ in 0..n {
                    current = parents[current].ok_or("cycle predecessor missing")?.source;
                }
                let origin = current;
                let mut nodes = vec![self.nodes[current].as_str()];
                let mut path = Vec::new();
                let mut cost = 0;
                for _ in 0..=n {
                    let edge = parents[current].ok_or("cycle predecessor missing")?;
                    path.push(edge.id.as_str());
                    cost += edge.cost;
                    current = edge.source;
                    nodes.push(&self.nodes[current]);
                    if current == origin {
                        break;
                    }
                }
                require(
                    current == origin && cost < 0,
                    "invalid negative-cycle witness",
                )?;
                nodes.reverse();
                path.reverse();
                return Ok(
                    json!({"status":"negative_cycle","from":query.source,"to":query.target,"cycle":{"nodes":nodes,"edges":path,"cost":cost},"passes":passes}),
                );
            }
        }
        let Some(cost) = distances[destination] else {
            let mut reachable = vec![false; n];
            reachable[start] = true;
            for _ in 0..n {
                for edge in &edges {
                    if reachable[edge.source] {
                        reachable[edge.target] = true;
                    }
                }
            }
            let (mut reached, mut unavailable) = (Vec::new(), Vec::new());
            for (i, name) in self.nodes.iter().enumerate() {
                if reachable[i] {
                    reached.push(name);
                } else {
                    unavailable.push(name);
                }
            }
            reached.sort();
            unavailable.sort();
            return Ok(
                json!({"status":"unreachable","from":query.source,"to":query.target,"passes":passes,"diagnosis":{"reachable_count":reached.len(),"reachable":reached,"unreachable":unavailable,"open_edges":edges.len(),"reason":"destination is outside the source's reachable component"}}),
            );
        };
        let mut current = destination;
        let mut nodes = vec![self.nodes[current].as_str()];
        let mut path = Vec::new();
        let mut seen = vec![false; n];
        seen[current] = true;
        while current != start {
            let edge = parents[current].ok_or("route predecessor is missing")?;
            path.push(edge.id.as_str());
            current = edge.source;
            require(!seen[current], "finite route contains a cycle")?;
            seen[current] = true;
            nodes.push(&self.nodes[current]);
            require(nodes.len() <= n, "route exceeds node bound")?;
        }
        nodes.reverse();
        path.reverse();
        Ok(
            json!({"status":"ok","from":query.source,"to":query.target,"cost":cost,"nodes":nodes,"edges":path,"passes":passes,"relaxations":relaxations}),
        )
    }
}
fn explain(result: &Value) -> String {
    let heading = format!(
        "{} -> {}: ",
        result["from"].as_str().unwrap(),
        result["to"].as_str().unwrap()
    );
    let message = match result["status"].as_str().unwrap() {
        "closed" => "an endpoint is closed".into(),
        "unreachable" => "no directed path remains after closures".into(),
        "negative_cycle" => {
            "no finite minimum; a reachable negative cycle can lead to the destination".into()
        }
        _ => format!(
            "cost {} via {}",
            result["cost"],
            result["nodes"]
                .as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_str().unwrap())
                .collect::<Vec<_>>()
                .join(" -> ")
        ),
    };
    heading + &message
}
fn run() -> Result<i32> {
    let input =
        rt::read_text(&std::env::var("ROUTE_INPUT").unwrap_or_else(|_| "graph.json".into()))?;
    let input: Input = serde_json::from_value(rt::json_loads(&input)?)?;
    let graph = Graph::new(input.nodes, input.edges)?;
    require(
        (1..=100).contains(&input.queries.len()),
        "expected 1–100 route queries",
    )?;
    let mut results = Vec::with_capacity(input.queries.len());
    let mut explanations = Vec::new();
    let mut failures = 0;
    for query in &input.queries {
        let result = graph.solve(query)?;
        if result["status"] != "ok" {
            failures += 1;
        }
        explanations.push(explain(&result));
        results.push(result);
    }
    let report =
        json!({"routes":results,"queries":input.queries.len(),"without_finite_route":failures});
    let pretty = rt::pretty(&report)?;
    rt::write_text_atomic(
        &std::env::var("ROUTE_REPORT").unwrap_or_else(|_| "routes.json".into()),
        &pretty,
    )?;
    rt::write_text_atomic(
        &std::env::var("ROUTE_TEXT").unwrap_or_else(|_| "routes.txt".into()),
        &(explanations.join("\n") + "\n"),
    )?;
    println!("{pretty}");
    Ok(i32::from(failures > 0))
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
