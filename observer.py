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

def connect_with_retry(
	server_address,
	socket_factory=socket.socket,
	monotonic=time.monotonic,
	sleeper=time.sleep,
	total_timeout=120.0,
	retry_interval=1.0,
):
	deadline = monotonic() + total_timeout
	last_error = None

	while True:
		sock = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
		try:
			if hasattr(sock, "settimeout"):
				sock.settimeout(min(5.0, max(1.0, deadline - monotonic())))
			sock.connect(server_address)
			return sock
		except OSError as err:
			last_error = err
			sock.close()
			if monotonic() + retry_interval > deadline:
				raise RuntimeError(f"failed to connect to {server_address[0]}:{server_address[1]} within {total_timeout:.0f}s: {last_error}")
			sleeper(retry_interval)

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

def node_ip(blockchain: str, n: int) -> str:
	"""Return the IP address for 0-indexed node n of the given blockchain."""
	if blockchain.startswith("hotstuff") or blockchain.startswith("asonnino-hotstuff"):
		# HotStuff nodes: 10.30.10.1 through 10.30.10.10
		return f"10.30.10.{n + 1}"
	else:
		# Original scheme for avalanche et al.: 10.40.{10|11}.{n+1}
		return f"10.40.{10 if n < 10 else 11}.{n + 1}"

def start_loss(nodenum: int, node: int, failures: int, blockchain: str):
	this = list(range(nodenum - failures))
	other = list(range(nodenum - failures, nodenum))
	if node in other:
		this, other = other, this
	subprocess.run(shlex.split("sudo tc qdisc add dev eth0 root handle 1: prio"))
	print(f"other: {other}")
	for n in other:
		ip = node_ip(blockchain, n)
		subprocess.run(shlex.split(f"sudo tc filter add dev eth0 protocol ip parent 1:0 prio 3 u32 match ip dst {ip} flowid 1:3"))
	subprocess.run(shlex.split("sudo tc qdisc add dev eth0 parent 1:3 handle 30: netem loss 100%"))

def stop_loss():
	subprocess.run(shlex.split("sudo tc qdisc del dev eth0 root"))

class Mode(str, Enum):
	none = "none"
	crash = "crash"
	crash_no_recovery = "crash-no-recovery"
	partition = "partition"

def parse_args(argv=None):
	parser = ArgumentParser()
	parser.add_argument('ip', type=str)
	parser.add_argument('port', type=int)
	parser.add_argument('script', type=str)
	parser.add_argument('failures', type=int)
	parser.add_argument('downtime', type=int)
	parser.add_argument('mode', type=Mode)
	parser.add_argument('nodenum', type=int)
	return parser.parse_args(argv)

def main(argv=None):
	args = parse_args(argv)
	s = sched.scheduler()
	server_address = (args.ip, args.port)
	script = args.script
	failures = args.failures
	downtime = args.downtime
	mode = args.mode
	nodenum = args.nodenum

	blockchain = Path(script).name

	# redundant interfaces share deploy directories with their base chain.
	if blockchain.startswith("hotstuff"):
		deploy_blockchain = "hotstuff"
	elif blockchain.startswith("asonnino-hotstuff"):
		deploy_blockchain = "asonnino-hotstuff"
	else:
		deploy_blockchain = blockchain
	deploy_path = Path.home() / "deploy" / deploy_blockchain
	nodes = [int(x.name.removeprefix("n")) for x in deploy_path.iterdir() if x.is_dir() and x.name.startswith("n")]
	if len(nodes) != 1:
		print(f'expected exactly one local node directory under {deploy_path}, found {nodes}', file=sys.stderr)
		sys.exit(1)
	node = nodes[0]

	print(f'connecting to {server_address[0]} port {server_address[1]}, script {script}, blockchain {blockchain}, node {node}', flush=True)
	with connect_with_retry(server_address) as sock:
		print('connected', flush=True)

		msg = recv_exact(sock, 8)
		(duration,) = struct.unpack('<d', msg)
		print(f'received duration {duration}', flush=True)
		now = time.monotonic()
		fault_at = duration / 6.0
		recovery_at = duration / 3.0
		print(f'fault_at={fault_at:.1f}s recovery_at={recovery_at:.1f}s', flush=True)

		match mode:
			case Mode.crash:
				s.enterabs(now + fault_at, 0, call_script, (script, "kill", list(range(nodenum - failures, nodenum)),))
				s.enterabs(now + recovery_at, 0, call_script, (script, "start", list(range(nodenum - failures, nodenum)),))
			case Mode.crash_no_recovery:
				s.enterabs(now + fault_at, 0, call_script, (script, "kill", list(range(nodenum - failures, nodenum)),))
			case Mode.partition:
				s.enterabs(now, 0, lambda: subprocess.run(shlex.split("sudo ethtool -K eth0 tso off gso off gro off sg off")))
				s.enterabs(now + fault_at, 0, start_loss, (nodenum, node, failures, blockchain,))
				s.enterabs(now + recovery_at, 0, stop_loss)
			case Mode.none:
				pass

		s.enterabs(now + duration, 0, lambda: print('done!', flush=True))
		s.run()

if __name__ == "__main__":
	main()
