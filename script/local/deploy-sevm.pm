package deploy_sevm;

use strict;
use warnings;

use File::Copy;
use YAML;

use Minion::System::Pgroup;


my $FLEET = $_;						# Global parameter (setup by the Runner)
my %PARAMS = @_;					# Script parameters (setup by the Runner)
my $RUNNER = $PARAMS{RUNNER};		# Runner itself (setup by the Runner)


my $MINION_SHARED = $ENV{MINION_SHARED};        # Environment (setup by Runner)
my $MINION_PRIVATE = $ENV{MINION_PRIVATE};  # Where to store local private data

my $DATA_DIR = $MINION_SHARED . '/sevm';  # Where to store things across
												 # Runner invocations

my $ROLES_NAME = 'behaviors.txt';
my $ROLES_PATH = $DATA_DIR . '/' . $ROLES_NAME;	# Behaviors of workers
my $SETUP_PATH = $DATA_DIR . '/setup.yaml';		# Diablo description of the chain
my $ROLES_PUBLIC_PATH = $DATA_DIR . '/behaviors-new.txt';		# Behaviors of workers with public IP addresses


my $DEPLOY_ROOT = 'deploy/sevm';	# Where the files are deployed on
									# the workers
my $ROLES_LOC = $DEPLOY_ROOT . '/' . $ROLES_NAME;

# Directory containing nodes data directories
#
my $NETWORK_NAME = 'network';
my $NETWORK_PATH = $MINION_PRIVATE . '/' . $NETWORK_NAME;
my $NETWORK_LOC = $DEPLOY_ROOT . '/' . $NETWORK_NAME;

my $KEYS_ROOT = 'install/geth-accounts';
my $KEYS_TXT_LOC = $KEYS_ROOT . '/accounts.txt';
my $KEYS_YAML_LOC = $KEYS_ROOT . '/accounts.yaml';


# Extract from the given $path the SEVM nodes.
#
# Return: { $ip => { 'worker' => $worker
#                  , 'number' => $number
#                  }
#         }
#
#   where $ip is an IPv4 address, $worker is a Minion::Worker object and
#   $number indicates the number of instances to deploy on $worker.
#
sub get_nodes
{
	my ($path) = @_;
	my (%nodes, $node, $fh, $line, $ip, $number, $worker, $assigned);

	if (!open($fh, '<', $path)) {
	die ("cannot open '$path' : $!");
	}

	my $index = 0;
	while (defined($line = <$fh>)) {
	chomp($line);
	($ip, $number) = split(':', $line);
	$node = $nodes{$ip};

	if (defined($node)) {
		$node->{'number'} += $number;
		next;
	}

	$assigned = undef;

	foreach $worker ($FLEET->members()) {
		if ($worker->can('public_ip') && ($worker->public_ip() eq $ip)) {
		$assigned = $worker;
		last;
		} elsif ($worker->can('host') && ($worker->host() eq $ip)) {
		$assigned = $worker;
		last;
		}
	}

	if (!defined($assigned)) {
		die ("cannot find worker with ip '$ip' in deployment fleet");
	}

	$nodes{$ip} = {
		'worker' => $assigned,
		'number' => $number,
		'index' => $index
	};
	$index += 1;
	}

	close($fh);

	return \%nodes;
}

sub generate_setup
{
	my ($network, $nodes, $target, $redundancy) = @_;
	my ($ofh, $document, $line, $worker, %groups, $tags);

	my $index = 0;
	foreach my $ip (sort { $nodes->{$a}->{'index'} <=> $nodes->{$b}->{'index'} } keys %$nodes) {
		for (my $i = 0; $i < $nodes->{$ip}->{'number'}; $i++) {
			my $path = $network . '/n' . $index . '/wsport';
			my ($rfh, $port);
			if (!open($rfh, '<', $path)) {
				die ("cannot read '$path' : $!");
			}

			chomp($port = <$rfh>);
			close($rfh);

			if ($port !~ /^\d+$/) {
				die ("corrupted file '$path' : '$port'");
			}

			$line = sprintf("%s:%d", $ip, $port);
			$tags = $nodes->{$ip}->{'worker'}->region() . sprintf("\n%d\nn%d", $port, $nodes->{$ip}->{'index'});
			push(@{$groups{$tags}}, $line);

			$index += 1;
		}
	}

	if (!open($ofh, '>', $target)) {
		return 0;
	}

	printf($ofh "interface: \"ethereum\"\n");
	printf($ofh "\n");
	printf($ofh "parameters:\n");
	printf($ofh "  redundancy: %d\n", $redundancy);
    printf($ofh "\n");
	printf($ofh "endpoints:\n");

	foreach $tags (keys(%groups)) {
		printf($ofh "\n");
		printf($ofh "  - addresses:\n");
		foreach $line (@{$groups{$tags}}) {
			printf($ofh "    - %s\n", $line);
		}
		printf($ofh "    tags:\n");
		foreach $line (split("\n", $tags)) {
			printf($ofh "    - %s\n", $line);
		}
	}

	close($ofh);

	return 1;
}

# Dispatch the content of the given network to the workers.
#
sub dispatch
{
	my ($nodes, $network) = @_;
	my @procs;

	my $index = 0;
	foreach my $node (sort { $a->{'index'} <=> $b->{'index'} } values %$nodes) {
		my @paths = ();

		for (my $i = 0; $i < $node->{'number'}; $i++) {
			push(@paths, $network . '/n' . $index);
			$index += 1;
		}

		my $proc = $node->{'worker'}->send([ @paths ], TARGET => $DEPLOY_ROOT);
		push(@procs, $proc);
	}

	my @stats = Minion::System::Pgroup->new(\@procs)->waitall();

	if (grep { $_->exitstatus() != 0 } @stats) {
	die ("cannot dispatch sevm network to workers");
	}
}

sub generate_behaviors
{
	my ($nodes, $target) = @_;
	my $ofh;

	if (!open($ofh, '>', $target)) {
		return 0;
	}

	foreach my $ip (sort { $nodes->{$a}->{'index'} <=> $nodes->{$b}->{'index'} } keys %$nodes) {
		printf($ofh "%s:%d\n", $ip, $nodes->{$ip}->{'number'});
	}

	close($ofh);

	return 1;
}

# Deploy an SEVM blockchain over the workers listed in $ROLES_PATH which
# are in the given $FLEET.
#
sub deploy_sevm
{
	my ($genworker, $proc);

	# No node with SEVM behavior.
	# We exit with success.
	#
	if (!(-f $ROLES_PATH)) {
	return 1;
	}

	my ($redundancy, @err) = @ARGV;

	if (not defined $redundancy) {
		die ("redundancy name not defined")
	}

	if (@err) {
		die ("unexpected argument '" . shift(@err) . "'");
	}

	# Get workers and number of nodes on each worker from role file.
	#
	my $nodes = get_nodes($ROLES_PATH);
	my @workers = map { $_->{'worker'} } values(%$nodes);

	# Prepare SEVM deployment for all nodes.
	#
	$proc = $RUNNER->run(\@workers, [ 'deploy-sevm-worker','prepare' ]);
	if ($proc->wait() != 0) {
	die ("failed to prepare sevm workers");
	}

	# Generate network for SEVM

	$genworker = $workers[0];

	generate_behaviors($nodes, $ROLES_PUBLIC_PATH);
	$proc = $genworker->send([ $ROLES_PUBLIC_PATH ], TARGET => $ROLES_LOC);
	if ($proc->wait() != 0) {
	die ("cannot send sevm node file to worker");
	}

	$proc = $RUNNER->run(
	$genworker,
	[ 'deploy-sevm-worker', 'generate', $ROLES_LOC ]
	);
	if ($proc->wait() != 0) {
	die ("failed to generate sevm testnet");
	}

	# Fetch and dispatch generated testnet

	$proc = $genworker->recv([ $NETWORK_LOC . '.tar.gz' ], TARGET => $MINION_PRIVATE);
	if ($proc->wait() != 0) {
	die ("cannot receive sevm testnet from worker");
	}
	$proc = $genworker->recv(
    [ $KEYS_YAML_LOC ],
    TARGET => $DATA_DIR . '/accounts.yaml'
    );
    if ($proc->wait() != 0) {
        die ("cannot receive poa accounts from worker");
    }

	system('tar', '--directory=' . $ENV{MINION_PRIVATE}, '-xzf',
		$ENV{MINION_PRIVATE} . '/' . $NETWORK_NAME . '.tar.gz');

	generate_setup($NETWORK_PATH, $nodes, $SETUP_PATH, $redundancy);

	dispatch($nodes, $NETWORK_PATH);

	$genworker->execute(
	[ 'rm', '-rf', $ROLES_LOC, $NETWORK_LOC . '.tar.gz' ]
	)->wait();

	if (!unlink($ROLES_PATH)) {
	return 0;
    }

	if (!unlink($ROLES_PUBLIC_PATH)) {
	return 0;
    }

	return 1;
}


deploy_sevm();
__END__
