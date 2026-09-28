import os
import urllib.request


class ShellTool:
    def run(self, command):
        return os.popen(command).read()


class HttpTool:
    def get(self, url):
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode()


class RefundTool:
    def refund(self, order_id, amount_cents):
        return {"order_id": order_id, "amount_cents": amount_cents, "status": "queued"}
