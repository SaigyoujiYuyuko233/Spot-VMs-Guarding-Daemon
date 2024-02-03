class IApiClient:
    def __init__(self, endpoint):
        self.endpoint = endpoint
        pass

    def login(self, access_id, access_key):
        raise Exception("Not implemented")
    
    def create_vm(self, config):
        raise Exception("Not implemented")
