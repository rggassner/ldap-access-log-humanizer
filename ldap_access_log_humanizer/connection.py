import re
from ldap_access_log_humanizer.file_descriptor import FileDescriptor
from ldap_access_log_humanizer.operation import Operation
from ldap_access_log_humanizer.custom_logger import CustomLogger


class Connection:
    def __init__(self, conn_id, args_dict):
        self.conn_id = conn_id
        self.time = ""
        self.server = ""
        self.process = ""
        self.operations = {}
        self.tls_status = False
        self.file_descriptors = []
        self.logger = CustomLogger(args_dict)
        self.authenticated_status = False
        self.user = ""

    def dict(self):
        return {
            "conn_id": self.conn_id,
            "time": self.time,
            "client": self.client(),
            "server": self.server,
            "tls": self.tls(),
            "authenticated": self.authenticated(),
            "user": self.user
        }

    def reconstitute(self, event_dict):
        combined_dict = {}
        combined_dict.update(self.dict())
        combined_dict.update(event_dict)
        return combined_dict

    def authenticated(self):
        mail_regex = r'.*mail=([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)'
        uid_regex = r'.*uid=([a-zA-Z0-9._-]+)'

        # requirements: single operation where we have a BIND verb followed by an LDAP_SUCCESS
        for operation in self.operations.values():
            for request in operation.requests:
                if request.get("verb") == "BIND":
                    # Set user (even if they aren't authenticated, so we can track attempts)
                    for detail in request.get("details"):
                        mail_match_object = re.match(mail_regex, detail)
                        if mail_match_object:
                            self.user = mail_match_object.group(1)

                        uid_match_object = re.match(uid_regex, detail)
                        if uid_match_object:
                            self.user = uid_match_object.group(1)

                    # Set status if that user was successful
                    if operation.response_verb == "RESULT" and operation.error == "LDAP_SUCCESS":
                        self.authenticated_status = True

        return self.authenticated_status

    def tls(self):
        for file_descriptor in self.file_descriptors:
            if file_descriptor.verb == "TLS" and file_descriptor.details.startswith("established"):
                self.tls_status = True

        return self.tls_status

    def closed(self):
        for file_descriptor in self.file_descriptors:
            if file_descriptor.verb == "closed":
                return True

        return False

    def client(self):
        for file_descriptor in self.file_descriptors:
            if file_descriptor.verb == "ACCEPT":
                pattern = r'from IP=(\d+\.\d+\.\d+\.\d+):'
                match = re.search(pattern, file_descriptor.details)
                if match:
                    return match.group(1)

        return ""


    def add_operation(self, rest):
        # Expecting something like:
        # op=1 BIND dn="uid=bind-generateusers,ou=logins,dc=example" mech=SIMPLE ssf=0
        pattern = r'^op=(\d+) (.*)$'
        match = re.search(pattern, rest)

        if not match:
            raise Exception('Malformed operation: {}'.format(rest))

        op_id = int(match.group(1))
        details = match.group(2)

        operation = self.operations.get(op_id)

        if operation:
            operation.add_event(details)
        else:
            operation = Operation(op_id)
            operation.add_event(details)
            self.operations[op_id] = operation

        # Once the operation is complete and loggable, log and discard it
        if operation.loggable():
            self.logger.log(self.reconstitute(operation.dict()))
            del self.operations[op_id]  # Free memory by removing it


    def add_file_descriptor(self, rest):
        # Expecting something like:
        # fd=34 ACCEPT from IP=192.168.1.1:56822 (IP=0.0.0.0:389)
        #
        pattern = r'^fd=(\d+) (.*)$'
        match = re.search(pattern, rest)

        if match:
            file_descriptor = FileDescriptor(int(match.group(1)))
            file_descriptor.add_event(match.group(2))
            self.file_descriptors.append(file_descriptor)

            if file_descriptor.loggable():
                self.logger.log(self.reconstitute(file_descriptor.dict()))
        else:
            raise Exception('Malformed file file_descriptor: {}'.format(rest))

    # Something happened, this method's job is to update the context
    def add_event(self, event):
        self.time = event['time']
        self.server = event['server']
        self.process = event['process']
        self.add_rest(event['rest'])

    def add_rest(self, rest):
        if rest.startswith('op'):
            self.add_operation(rest)
        elif rest.startswith('fd'):
            self.add_file_descriptor(rest)
        else:
            raise Exception('Unsupported option: {}'.format(rest))
