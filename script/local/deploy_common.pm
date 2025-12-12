package deploy_common;

use strict;
use warnings;

my $FLEET = $_;                        # Global parameter (setup by the Runner)


# Extract from the given $path the nodes.
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
	    'number' => $number
	};
    }

    close($fh);

    return \%nodes;
}
