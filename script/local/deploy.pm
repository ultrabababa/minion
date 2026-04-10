package deploy;

use strict;
use warnings;


my $FLEET = $_;
my %PARAMS = @_;
my $RUNNER = $PARAMS{RUNNER};
my $MINION_SHARED = $ENV{MINION_SHARED} || '/tmp/minion_shared';

my ($redundancy, @err) = @ARGV;

if (@err) {
    die ("unexpected argument '" . shift(@err) . "'");
}


# Remove the previous deployment directory to start from a clean one.
#

$FLEET->execute(['rm', '-rf', 'deploy'], STDERRS => '/dev/null')->waitall();

# Clear potentially stale local setup files to avoid selecting wrong blockchain interface.
unlink($MINION_SHARED . '/hotstuff/setup.yaml');
unlink($MINION_SHARED . '/asonnino-hotstuff/setup.yaml');
unlink($MINION_SHARED . '/asonnino-hotstuff-redundant/setup.yaml');

# Deploy the blockchains that have been enabled by 'behave-*' scripts.
# Do nothing if not enabled.
#

if ($RUNNER->run($FLEET, [ 'deploy-algorand', $redundancy ])->wait() != 0) {
    die ("failed to deploy algorand");
}

if ($RUNNER->run($FLEET, [ 'deploy-aptos', $redundancy ])->wait() != 0) {
    die ("failed to deploy algorand");
}

if ($RUNNER->run($FLEET, [ 'deploy-solana', $redundancy ])->wait() != 0) {
    die ("failed to deploy solana");
}

if ($RUNNER->run($FLEET, [ 'deploy-avalanche', $redundancy ])->wait() != 0) {
    die ("failed to deploy avalanche");
}

if ($RUNNER->run($FLEET, [ 'deploy-sevm', $redundancy ])->wait() != 0) {
    die ("failed to deploy avalanche");
}

if (-f ($MINION_SHARED . '/hotstuff/behaviors.txt')) {
    if ($RUNNER->run($FLEET, [ 'deploy-hotstuff', $redundancy ])->wait() != 0) {
        die ("failed to deploy hotstuff");
    }
}

if (-f ($MINION_SHARED . '/asonnino-hotstuff/behaviors.txt')) {
    if ($RUNNER->run($FLEET, [ 'deploy-asonnino-hotstuff', $redundancy ])->wait() != 0) {
        die ("failed to deploy asonnino-hotstuff");
    }
}

if (-f ($MINION_SHARED . '/hotstuff-redundant/behaviors.txt')) {
    if ($RUNNER->run($FLEET, [ 'deploy-hotstuff-redundant', $redundancy ])->wait() != 0) {
        die ("failed to deploy hotstuff-redundant");
    }
}

if (-f ($MINION_SHARED . '/asonnino-hotstuff-redundant/behaviors.txt')) {
    if ($RUNNER->run($FLEET, [ 'deploy-asonnino-hotstuff-redundant', $redundancy ])->wait() != 0) {
        die ("failed to deploy asonnino-hotstuff-redundant");
    }
}

# Deploy diablo at the very end as it might need some configuration generated
# by the deployment of other blockchains.
#

if ($RUNNER->run($FLEET, [ 'deploy-diablo' ])->wait() != 0) {
    die ("failed to deploy diablo");
}


1;
__END__
