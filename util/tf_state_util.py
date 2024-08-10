def find_resource_by_path(resources: list, path: str):
    nodes = path.split(".")

    for r in resources:
        if r["type"] == nodes[0] and r["name"] == nodes[1]:
            return r["instances"][0]["attributes"]

    return None
