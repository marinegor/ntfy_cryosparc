#!/usr/bin/env python3
"""
Very simple HTTP server in pure python for processing local cryosparc notifications
Usage::
    ./server.py [<port>]
"""

# ----------------------
# The logic starts here, since the mode of running within cryosparc environment
# doesn't work properly with `if __name__ == 'main'` idiom
# ----------------------

import socket
import argparse
import logging

logging.basicConfig(level=logging.DEBUG)


# Custom usage message to run within cryosparc context
usage = "usage: cryosparcm call python3 server.py [-h] [--url URL] [--admin ADMIN] [--hostname HOSTNAME]"


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter, usage=usage
)
parser.add_argument(
    "--url",
    type=str,
    default="https://ntfy.sh",
    help="location of ntfy server (change from default if you're self-hosting it",
)
parser.add_argument(
    "--admin",
    type=str,
    default="admin",
    help="username for admin messages (like when a notification is failed to get parsed)",
)
parser.add_argument(
    "--hostname",
    type=str,
    default=socket.gethostname(),
    help="master node hostname, is used in notification channel name: <url>/cs_<hostname>_<username>",
)

args = parser.parse_args()

# ----------------------
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import os
import json
from typing import Tuple, Optional

from cryosparc_compute.client import CommandClient

cli = CommandClient(
    os.getenv("CRYOSPARC_MASTER_HOSTNAME"),
    int(os.getenv("CRYOSPARC_COMMAND_CORE_PORT")),
)

Response = requests.models.Response


class NtfyException(BaseException):
    pass


def job2username(p: str, j: str) -> str:
    try:
        rv = cli.get_username_by_id(
            cli.get_job(p.upper(), j.upper()).get("created_by_user_id")
        )
        if rv is None:
            raise NtfyException(
                f"Error parsing response of cli.get_job(p={p}, j={j}): no 'created_by_user_id' field"
            )
        return rv
    except:
        raise NtfyException(f"Couldn't find user for P={p}, J={j}")


def job2type(p: str, j: str) -> str:
    try:
        rv = cli.get_job(p.upper(), j.upper()).get("job_type")
        if rv is None:
            raise NtfyException(
                f"Error parsing response of cli.get_job(p={p}, j={j}): no 'job_type' field"
            )
        return rv
    except:
        raise NtfyException(f"Couldn't find user for P={p}, J={j}")


def get_project_title(p: str) -> str:
    try:
        rv = cli.get_project(p).get("title", p)
        return rv
    except ValueError:
        raise NtfyException(f"Couldn't get project name for P={p}")


class Ntfy:
    def __init__(
        self,
        url: str,
        hostname: str,
        admin: str,
    ):
        self.source = f"{url}/cs_{hostname}"
        self.admin = admin
        logging.info(f'Posting alerts to {self.source}_"your_cryosparc_username"')

    def __repr__(self) -> str:
        return f"Ntfy(source={self.source}, admin={self.admin})"

    def __str__(self) -> str:
        return repr(self)

    def create_message_from_response(self, d: dict) -> Tuple[str, str, str]:
        assert "text" in d, d
        s = d["text"]
        project, job, *status = s.split()
        status = " ".join(status)
        job_type = job2type(p=project, j=job)

        user = job2username(p=project, j=job)
        header = s
        message = (
            f"Project: {get_project_title(project)}\nJob: {job_type}\nStatus: {status}"
        )

        return user, header, message

    def post(self, header: str, message: str, user: str, priority: str) -> Response:
        assert priority in ("max", "urgent", "high", "default", "low", "min"), priority

        url = f"{self.source}_{user}"
        headers = {"Title": header, "Priority": priority}
        target = f"{self.source}_{user}"
        logging.info(f"posting to url={url} message={message} with headers={headers}")
        rv = requests.post(
            target, data=message.encode(encoding="utf-8"), headers=headers
        )
        return rv

    def post_default(self, header: str, message: str, user: str) -> Response:
        return self.post(header=header, message=message, user=user, priority="min")

    def post_alert(self, header: str, message: str, user: str) -> Response:
        return self.post(header=header, message=message, user=user, priority="max")

    def process(self, data: dict) -> Optional[Response]:
        try:
            user, header, message = self.create_message_from_response(data)
        except Exception as e:
            msg = f"Error processing data={data}: {e.__repr__()}"
            self.post_alert(header="Alert", message=msg, user=self.admin)
            raise NtfyException(msg)

        return self.post_default(user=user, header=header, message=message)


class S(BaseHTTPRequestHandler):
    def _set_response(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        logging.info(
            "GET request,\nPath: %s\nHeaders:\n%s\n", str(self.path), str(self.headers)
        )
        self._set_response()
        self.wfile.write("GET request for {}".format(self.path).encode("utf-8"))

    def do_POST(self):
        content_length = int(
            self.headers["Content-Length"]
        )  # <--- Gets the size of data
        post_data = self.rfile.read(content_length)  # <--- Gets the data itself
        data = json.loads(post_data.decode("utf-8"))

        logging.info(f"Got following json:\n{data}")
        logging.info(
            "POST request,\nPath: %s\nHeaders:\n%s\n\nBody:\n%s\n",
            str(self.path),
            str(self.headers),
            data,
        )

        try:
            ntfy.process(data)
        except NtfyException as e:
            message = f"Got error {e} while trying to process data={data}"
            ntfy.post_alert(message=message, header="Alert", user=ntfy.admin)
            logging.error(message)

        self._set_response()
        self.wfile.write("POST request for {}".format(self.path).encode("utf-8"))


def run(server_class=HTTPServer, handler_class=S, port: int = 8000):
    logging.basicConfig(level=logging.INFO)
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logging.info(f"Starting httpd on port {port}...\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        ntfy.post_default(
            message=f"KeyboardInterrupt detected, ntfy instance: {ntfy}",
            header="info",
            user=ntfy.admin,
        )
    httpd.server_close()
    logging.info("Stopping httpd...\n")


cs_webhook = os.getenv("CRYOSPARC_SLACK_WEBHOOK_URL")
logging.info(f"CRYOSPARC_SLACK_WEBHOOK_URL={cs_webhook}")
port = int(cs_webhook.split(":")[-1])

ntfy = Ntfy(url=args.url, hostname=args.hostname, admin=args.admin)

logging.info(f"Running instance: {ntfy}")
logging.info(f"Admin notifications channel: {ntfy.source}_{ntfy.admin}")
run(port=port)
