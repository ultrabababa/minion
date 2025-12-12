from argparse import ArgumentParser
from enum import Enum
import sched
import shlex
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

def recv_exact(sock: socket.socket, msglen: int):
	chunks = []
	bytes_recd = 0
	while bytes_recd < msglen:
		chunk = sock.recv(min(msglen - bytes_recd, 2048))
		if chunk == b'':
			raise RuntimeError("socket connection broken")
		chunks.append(chunk)
		bytes_recd = bytes_recd + len(chunk)
	return b''.join(chunks)

def call_script(script: str, action: str, nodes: list[int]):
	p = subprocess.run([script, action] + [str(i) for i in nodes], capture_output=True)
	print(f'script: {script} action: {action} stdout: {p.stdout.decode()} stderr: {p.stderr.decode()}')

def start_loss(nodenum: int, node: int, failures: int):
	this = list(range(nodenum - failures))
	other = list(range(nodenum - failures, nodenum))
	if node in other:
		this, other = other, this
	subprocess.run(shlex.split("sudo tc qdisc add dev eth2 root handle 1: prio"))
	print(f"other: {other}")
	for n in other:
		subprocess.run(shlex.split(f"sudo tc filter add dev eth2 protocol ip parent 1:0 prio 3 u32 match ip dst 10.40.{10 if node < 10 else 11}.{n + 1} flowid 1:3"))
	subprocess.run(shlex.split("sudo tc qdisc add dev eth2 parent 1:3 handle 30: netem loss 100%"))

def stop_loss():
	subprocess.run(shlex.split("sudo tc qdisc del dev eth2 root"))

class Mode(str, Enum):
	none = "none"
	crash = "crash"
	crash_no_recovery = "crash-no-recovery"
	partition = "partition"

parser = ArgumentParser()
parser.add_argument('ip', type=str)
parser.add_argument('port', type=int)
parser.add_argument('script', type=str)
parser.add_argument('failures', type=int)
parser.add_argument('downtime', type=int)
parser.add_argument('mode', type=Mode)
parser.add_argument('nodenum', type=int)
args = parser.parse_args()

s = sched.scheduler()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
	server_address = (args.ip, args.port)
	script = args.script
	failures = args.failures
	downtime = args.downtime
	mode = args.mode
	nodenum = args.nodenum

	blockchain = Path(script).name

	nodes = [int(x.name.removeprefix("n")) for x in (Path.home() / "deploy" / blockchain).iterdir() if x.is_dir() and x.name.startswith("n")]
	if len(nodes) != 1:
		sys.exit(1)
	node = nodes[0]

	print(f'connecting to {server_address[0]} port {server_address[1]}, script {script}')
	sock.connect(server_address)
	print(f'connected')

	msg = recv_exact(sock, 8)
	(duration,) = struct.unpack('<d', msg)
	print(f'received duration {duration}')
	now = time.monotonic()
	middle = 200
	downtime = 400 / 3

	match mode:
		case Mode.crash:
			s.enterabs(now + middle - downtime / 2, 0, call_script, (script, "kill", list(range(nodenum - failures, nodenum)),))
			s.enterabs(now + middle + downtime / 2, 0, call_script, (script, "start", list(range(nodenum - failures, nodenum)),))
		case Mode.crash_no_recovery:
			s.enterabs(now + middle - downtime / 2, 0, call_script, (script, "kill", list(range(nodenum - failures, nodenum)),))
		case Mode.partition:
			s.enterabs(now, 0, lambda: subprocess.run(shlex.split("sudo ethtool -K eth2 tso off gso off gro off sg off")))
			s.enterabs(now + middle - downtime / 2, 0, start_loss, (nodenum, node, failures,))
			s.enterabs(now + middle + downtime / 2, 0, stop_loss)
			s.enterabs(now + duration, 0, lambda: subprocess.run(shlex.split("sudo ethtool -K eth2 tso on gso on gro on sg on")))
		case Mode.none:
			pass

	s.enterabs(now + duration, 0, lambda: print('done!'))

	s.run()
