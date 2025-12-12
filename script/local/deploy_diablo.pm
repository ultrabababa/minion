package deploy_diablo;

use strict;
use warnings;


my $FLEET = $_;                        # Global parameter (setup by the Runner)



# Extract from the given $path the Quorum nodes.
#
# Return: { $ip => { 'worker'      => $worker
#                  , 'primary'     => $primary
#                  , 'secondaries' => $secondaries
#                  }
#         }
#
#   where $ip is an IPv4 address, $worker is a Minion::Worker object, $primary
#   is '1' if the worker is primary and '0' if not, and $secondaries
#   indicates the number of secondary instances to deploy on $worker.
#
sub get_nodes
{
    my ($path) = @_;
    my (%nodes, $node, $fh, $line, $ip, $role, $number, $worker, $assigned);

    if (!open($fh, '<', $path)) {
	die ("cannot open '$path' : $!");
    }

    while (defined($line = <$fh>)) {
	chomp($line);
	($ip, $role, $number) = split(':', $line);

	$node = $nodes{$ip};

	if (!defined($node)) {
	    $assigned = undef;

	    foreach $worker ($FLEET->members()) {
		if ($worker->can('public_ip')) {
		    $assigned = $worker->public_ip();
		} elsif ($worker->can('host')) {
		    $assigned = $worker->host();
		}

		if ($assigned eq $ip) {
		    $assigned = $worker;
		    last;
		} else {
		    $assigned = undef;
		}
	    }

	    if (!defined($assigned)) {
		die ("cannot find worker with ip '$ip' in deployment fleet");
	    }

	    $node = {
		'worker' => $assigned,
		'primary' => 0,
		'secondary' => 0
	    };

	    $nodes{$ip} = $node;
	}

	if ($role eq 'primary') {
	    if ($number ne '1') {
		die ("malformed roles file '$path': $line");
	    }
	    $node->{'primary'} += 1;
	} elsif ($role eq 'secondary') {
	    $node->{'secondaries'} += $number;
	} else {
	    die ("malformed roles file '$path': $line");
	}
    }

    close($fh);

    $number = 0;
    foreach $ip (keys(%nodes)) {
	$number += $nodes{$ip}->{'primary'};
    }

    if ($number < 1) {
	die ("no primary node defined in '$path'");
    } elsif ($number > 1) {
	die ("multiple primary nodes defined in '$path'");
    }

    return \%nodes;
}
