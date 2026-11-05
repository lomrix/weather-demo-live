"""Offline walking-network comparison engine for saved scenario JSON."""

import heapq


def shortest_route(network, origin, destination, closed=None):
    connections = {}
    for link in network:
        if link["id"] in (closed or set()):
            continue
        if "walking" not in link["modes"]:
            continue
        for start, end in ((link["from"], link["to"]), (link["to"], link["from"])):
            connections.setdefault(start, []).append((link["metres"], end))

    queue = [(0, (origin,))]
    visited = set()
    while queue:
        distance, path = heapq.heappop(queue)
        node = path[-1]
        if node == destination:
            return {"metres": distance, "path": path}
        if node in visited:
            continue
        visited.add(node)
        for metres, neighbour in connections.get(node, []):
            if neighbour not in visited:
                heapq.heappush(queue, (distance + metres, (*path, neighbour)))
    return {"metres": None, "path": []}


def _validate_network(network):
    if not isinstance(network, list) or not network:
        raise ValueError("network must be a non-empty list")
    link_ids = set()
    endpoints = set()
    for link in network:
        _validate_link(link, link_ids)
        link_id = link["id"]
        link_ids.add(link_id)
        endpoints.update((link["from"], link["to"]))
    return link_ids, endpoints


def _validate_link(link, existing_ids):
    if not isinstance(link, dict):
        raise ValueError("each link must be an object")
    link_id = link.get("id")
    if (
        not isinstance(link_id, str)
        or not link_id.strip()
        or link_id in existing_ids
    ):
        raise ValueError("link IDs must be unique, non-empty strings")
    if (
        not isinstance(link.get("from"), str)
        or not link["from"].strip()
        or not isinstance(link.get("to"), str)
        or not link["to"].strip()
        or link["from"] == link["to"]
    ):
        raise ValueError(f"link {link_id}: endpoints must be distinct strings")
    if type(link.get("metres")) is not int or link["metres"] <= 0:
        raise ValueError(f"link {link_id}: metres must be a positive integer")
    modes = link.get("modes")
    if (
        not isinstance(modes, list)
        or not modes
        or not all(isinstance(mode, str) and mode.strip() for mode in modes)
    ):
        raise ValueError(f"link {link_id}: modes must be a non-empty list")


def _validate_journeys(journeys, endpoints):
    if not isinstance(journeys, list) or not journeys:
        raise ValueError("journeys must be a non-empty list")
    journey_ids = set()
    for journey in journeys:
        if not isinstance(journey, dict):
            raise ValueError("each journey must be an object")
        journey_id = journey.get("id")
        if not isinstance(journey_id, str) or not journey_id or journey_id in journey_ids:
            raise ValueError("journey IDs must be unique, non-empty strings")
        if journey.get("origin") not in endpoints or journey.get("destination") not in endpoints:
            raise ValueError(f"journey {journey_id}: endpoints must be in the network")
        journey_ids.add(journey_id)


def _validate_alternatives(alternatives, link_ids):
    if not isinstance(alternatives, list) or not alternatives:
        raise ValueError("alternatives must be a non-empty list")
    alternative_ids = set()
    for alternative in alternatives:
        if not isinstance(alternative, dict):
            raise ValueError("each alternative must be an object")
        alternative_id = alternative.get("id")
        if (
            not isinstance(alternative_id, str)
            or not alternative_id
            or alternative_id in alternative_ids
        ):
            raise ValueError("alternative IDs must be unique, non-empty strings")
        operations = alternative.get("operations")
        if not isinstance(operations, list) or not operations:
            raise ValueError(f"alternative {alternative_id}: operations are required")
        adds_links = any(
            isinstance(operation, dict) and operation.get("type") == "add_links"
            for operation in operations
        )
        if adds_links and alternative.get("hypothetical") is not True:
            raise ValueError(
                f"alternative {alternative_id}: add_links requires hypothetical true"
            )
        seen = set()
        for operation in operations:
            if not isinstance(operation, dict):
                raise ValueError(f"alternative {alternative_id}: operation must be an object")
            operation_type = operation.get("type")
            if operation_type not in {"close_links", "restrict_links", "add_links"}:
                raise ValueError(f"alternative {alternative_id}: unknown operation type")
            if operation_type == "add_links":
                if "links" not in operation or not isinstance(operation["links"], list):
                    raise ValueError(f"alternative {alternative_id}: add_links needs links")
                continue
            link_list = operation.get("link_ids")
            if not isinstance(link_list, list) or not link_list:
                raise ValueError(f"alternative {alternative_id}: link_ids are required")
            for link_id in link_list:
                if link_id not in link_ids:
                    raise ValueError(f"alternative {alternative_id}: unknown link ID {link_id}")
                if link_id in seen:
                    raise ValueError(
                        f"alternative {alternative_id}: ambiguous repeated link operation {link_id}"
                    )
                seen.add(link_id)
        alternative_ids.add(alternative_id)


def compare_scenario(scenario):
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    network = scenario.get("network")
    link_ids, endpoints = _validate_network(network)
    journeys = scenario.get("journeys")
    _validate_journeys(journeys, endpoints)
    alternatives = scenario.get("alternatives")
    _validate_alternatives(alternatives, link_ids)
    baseline = {}
    for journey in journeys:
        baseline[journey["id"]] = shortest_route(
            network, journey["origin"], journey["destination"]
        )
        if baseline[journey["id"]]["metres"] is None:
            raise ValueError(f"journey {journey['id']}: baseline destination is unreachable")

    results = []
    for alternative in alternatives:
        links = list(network)
        closed = set()
        added_ids = set()
        for operation in alternative["operations"]:
            operation_type = operation["type"]
            if operation_type == "close_links":
                mode = operation.get("mode")
                if mode != "walking":
                    raise ValueError(
                        f"alternative {alternative['id']}: close_links requires walking mode"
                    )
                closed.update(operation["link_ids"])
            elif operation_type == "restrict_links":
                if operation.get("mode") != "vehicle":
                    raise ValueError(
                        f"alternative {alternative['id']}: restrict_links requires vehicle mode"
                    )
            else:
                for link in operation["links"]:
                    try:
                        _validate_link(link, link_ids | added_ids)
                    except ValueError as exc:
                        raise ValueError(
                            f"alternative {alternative['id']}: invalid hypothetical walking link: {exc}"
                        ) from exc
                    if (
                        link["from"] not in endpoints
                        or link["to"] not in endpoints
                        or "walking" not in link["modes"]
                    ):
                        raise ValueError(
                            f"alternative {alternative['id']}: invalid hypothetical walking link"
                        )
                    links.append(link)
                    added_ids.add(link["id"])
        journey_results = []
        for journey in journeys:
            route = shortest_route(links, journey["origin"], journey["destination"], closed)
            change = None if route["metres"] is None else (
                route["metres"] - baseline[journey["id"]]["metres"]
            )
            journey_results.append({
                "journey_id": journey["id"],
                "baseline": baseline[journey["id"]],
                "route": route,
                "change_metres": change,
            })
        results.append({
            "id": alternative["id"],
            "label": alternative.get("label", alternative["id"]),
            "hypothetical": alternative.get("hypothetical", False),
            "journeys": journey_results,
        })
    return {
        "mode": "offline_scenario_comparison",
        "scenario": scenario.get("metadata", {}),
        "baseline": [
            {"journey_id": journey["id"], "route": baseline[journey["id"]]}
            for journey in journeys
        ],
        "alternatives": results,
    }
