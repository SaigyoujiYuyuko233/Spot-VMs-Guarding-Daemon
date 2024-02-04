from constant.terraform import INSTANCE_LABEL


def find_vm_instance(resources: list):
    for r in resources:
        if r["type"] in INSTANCE_LABEL:
            return r['instances'][0]['attributes']
    return None
