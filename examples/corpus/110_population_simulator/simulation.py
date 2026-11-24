"""Fixed-step RK4 integration with explicit stage guards and comparisons to the first case."""

from model import Experiment, Parameters

from py2rust.stdlib import Json


def slope(case: Parameters, population: float, timestep: float) -> float:
    assert 0.0 <= population <= 1e100, "population outside numerical domain"
    ratio: float = population / case.capacity if case.model == "logistic" else 0.0
    assert abs(case.rate) * timestep * max(1.0, ratio) <= 0.05, "timestep too large for current population"
    derivative: float = case.rate * population
    if case.model == "logistic":
        derivative = derivative * (1.0 - ratio)
    return derivative


def advance(case: Parameters, population: float, timestep: float) -> float:
    first: float = slope(case, population, timestep)
    second: float = slope(case, population + timestep * first / 2.0, timestep)
    third: float = slope(case, population + timestep * second / 2.0, timestep)
    fourth: float = slope(case, population + timestep * third, timestep)
    result: float = population + timestep * (first + 2.0 * second + 2.0 * third + fourth) / 6.0
    slope(case, result, timestep)
    return 0.0 if result == 0.0 else result


def simulate(experiment: Experiment) -> Json:
    times: list[float] = []
    for index in range(experiment.steps + 1):
        times.append(float(index) * experiment.timestep)
    results: list[Json] = []
    baseline: float = 0.0
    for index in range(len(experiment.cases)):
        case: Parameters = experiment.cases[index]
        population: float = case.initial
        slope(case, population, experiment.timestep)
        values: list[float] = [population]
        for step in range(experiment.steps):
            population = advance(case, population, experiment.timestep)
            values.append(population)
        if index == 0:
            baseline = population
        results.append(
            {
                "id": case.identifier,
                "name": case.name,
                "model": case.model,
                "values": values,
                "initial": case.initial,
                "final": population,
                "minimum": min(values),
                "maximum": max(values),
                "change": population - case.initial,
                "difference_from_first": population - baseline,
            }
        )
    return {
        "method": "rk4",
        "times": times,
        "series": results,
        "summary": {
            "cases": len(results),
            "steps": experiment.steps,
            "points": len(results) * len(times),
            "horizon": times[-1],
        },
    }
