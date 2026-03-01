package deploy_hotstuff;

use strict;
use warnings;
use File::Path qw(make_path);
use File::Basename;

my $FLEET = $_;
my %PARAMS = @_;
my $RUNNER = $PARAMS{RUNNER};

my ($action, @err) = @ARGV;

sub deploy_hotstuff
{
    my @hotstuff_ips = ();
    for (my $i = 1; $i <= 10; $i++) {
        push(@hotstuff_ips, "10.30.10.$i");
    }

    my @workers;
    foreach my $worker ($FLEET->members()) {
        my $ip = $worker->can('public_ip') ? $worker->public_ip() : $worker->host();
        if (grep { $_ eq $ip } @hotstuff_ips) {
            push(@workers, $worker);
        }
    }

    if (scalar(@workers) > 0) {
        my $proc = $RUNNER->run(\@workers, [ 'hotstuff', 'deploy' ]);
        if ($proc->wait() != 0) {
            die ("failed to deploy hotstuff on remote nodes");
        }
    }

    # Generate setup.yaml for Diablo
    my $SHARED = $ENV{MINION_SHARED} || '/tmp/minion_shared';
    my $setup_dir = "$SHARED/hotstuff";
    make_path($setup_dir) unless -d $setup_dir;
    
    my $setup_file = "$setup_dir/setup.yaml";
    open(my $fh, '>', $setup_file) or die "Cannot open $setup_file: $!";
    
    print $fh "interface: \"hotstuff\"\n";
    print $fh "\n";
    print $fh "endpoints:\n";
    print $fh "\n";
    print $fh "  - addresses:\n";
    foreach my $ip (@hotstuff_ips) {
        print $fh "    - $ip\n";
    }
    print $fh "    tags:\n";
    foreach my $ip (@hotstuff_ips) {
        print $fh "    - $ip\n";
    }
    close($fh);

    return 1;
}

deploy_hotstuff();
__END__
