"""Resolve a workload once and retain the exact generator state for reproducibility."""

# ruff: noqa: I001 - compact imports within the executable-project line budget
from randomness import Generator, draw
from py2rust.stdlib import Json, json_array, json_int, json_string


def resolve(workload: Json) -> tuple[list[Json], Json]:
    if json_string(workload["mode"]) == "explicit":
        return (json_array(workload["jobs"]), {"algorithm": "none", "seed": 0, "state": 0, "draws": 0})
    seed: int = json_int(workload["seed"])
    generator: Generator = Generator(seed, 0)
    jobs: list[Json] = []
    arrival: int = 0
    for index in range(json_int(workload["count"])):
        values: list[int] = []
        for field in ["gap", "service", "slack"]:
            bounds: list[Json] = json_array(workload[field])
            sampled: tuple[Generator, int] = draw(generator, json_int(bounds[0]), json_int(bounds[1]))
            generator = sampled[0]
            values.append(sampled[1])
        arrival = arrival + values[0]
        jobs.append(
            {"id": "job_" + str(index + 1), "arrival": arrival, "service": values[1], "deadline": arrival + values[2]}
        )
    return (
        jobs,
        {"algorithm": "park-miller-16807-v1", "seed": seed, "state": generator.state, "draws": generator.draws},
    )
