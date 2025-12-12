package deploy_diablo_observer;

use Cwd qw( abs_path );
use File::Basename qw( dirname );
use lib dirname( abs_path ( __FILE__ ) );
use strict;
use warnings;

use Getopt::Long qw(GetOptionsFromArray);
use List::Util qw(sum);
# use File::Copy;
# use YAML;

use Minion::System::Pgroup;
use deploy_common qw ( get_nodes );
use deploy_diablo qw ( get_nodes );


my $PRIMARY_TCP_PORT = 5002;


my $FLEET = $_;						# Global parameter (setup by the Runner)
my %PARAMS = @_;					# Script parameters (setup by the Runner)
my $RUNNER = $PARAMS{RUNNER};		# Runner itself (setup by the Runner)


my $SHARED = $ENV{MINION_SHARED};

my $DATA_DIR = $SHARED . '/diablo-observer';
my $ROLES_PATH = $DATA_DIR . '/behaviors.txt';

my $DIABLO_DATA_DIR = $SHARED . '/diablo';
my $DIABLO_ROLES_PATH = $DIABLO_DATA_DIR . '/behaviors.txt';


sub deploy_diablo_observer
{
	my ($blockchain, $failures, $mode) = @ARGV;

	if (not defined $blockchain) {
	die ("blockchain name not defined")
	}

	if (not defined $failures) {
	die ("number of failures not defined")
	}

	if (not defined $mode) {
	die ("mode not defined")
	}

	if (!(-e $ROLES_PATH)) {
	return 1;
    }

    my $nodes = deploy_common::get_nodes($ROLES_PATH);
	my $nodenum = sum(map { $_->{'number'} } values(%$nodes));
	my @workers = map { $_->{'worker'} } values(%$nodes);

	if (!(-e $DIABLO_ROLES_PATH)) {
	return 1;
    }

    my $diablo_nodes = deploy_diablo::get_nodes($DIABLO_ROLES_PATH);

	my $primary;
	foreach my $ip (keys(%$diablo_nodes)) {
	if ($diablo_nodes->{$ip}->{'primary'} > 0) {
	    $primary = $ip;
	    last;
	}
    }

	my $proc = $RUNNER->run(\@workers, [ 'deploy-diablo-observer-worker', $primary . ':' . $PRIMARY_TCP_PORT, $blockchain, $failures, $mode, $nodenum ]);
	if ($proc->wait() != 0) {
	die ("failed to deploy diablo observers");
	}
    my $pgrp = Minion::System::Pgroup->new([]);
	foreach my $worker (@workers) {
		$proc = Minion::System::Process->new(sub {
		exit ($worker->send(
			  [ 'script/remote/' . $blockchain ],
			  TARGET => 'deploy/diablo-observer/' . $blockchain
		      )->wait() >> 8);
	    });

	    $pgrp->add($proc);

		$proc = Minion::System::Process->new(sub {
		exit ($worker->send(
			  [ 'observer.py' ],
			  TARGET => 'deploy/diablo-observer/observer.py'
		      )->wait() >> 8);
	    });

	    $pgrp->add($proc);
	}
	if (grep { $_->exitstatus() != 0 } $pgrp->waitall()) {
	    fatal("cannot sync '" . 'script/remote/' . $blockchain . "'");
	}

	if (!unlink($ROLES_PATH)) {
	return 0;
    }

	return 1;
}


deploy_diablo_observer();
__END__
