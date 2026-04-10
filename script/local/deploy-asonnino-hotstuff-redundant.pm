package deploy_asonnino_hotstuff_redundant;

use strict;
use warnings;
use File::Path qw(make_path);

my $FLEET = $_;
my %PARAMS = @_;
my $RUNNER = $PARAMS{RUNNER};

my ($action, $redundancy, @err) = @ARGV;
$redundancy //= 1;

sub deploy_asonnino_hotstuff_redundant {
    my @ips = ();
    foreach my $worker ($FLEET->members()) {
        my $ip = $worker->can('public_ip') ? $worker->public_ip() : $worker->host();
        if ($ip =~ /^10\.30\.10\.\d+$/) {
            push(@ips, $ip);
        }
    }
    @ips = sort { 
        my ($a_end) = $a =~ /\.([^.]+)$/; 
        my ($b_end) = $b =~ /\.([^.]+)$/; 
        $a_end <=> $b_end 
    } @ips;

    my @workers;
    foreach my $worker ($FLEET->members()) {
        my $ip = $worker->can('public_ip') ? $worker->public_ip() : $worker->host();
        if (grep { $_ eq $ip } @ips) {
            push(@workers, $worker);
        }
    }

    if (@workers) {
        my $proc = $RUNNER->run(\@workers, [ 'asonnino-hotstuff', 'deploy' ]);
        if ($proc->wait() != 0) {
            die ("failed to deploy asonnino-hotstuff on remote nodes");
        }
    }

    my $SHARED = $ENV{MINION_SHARED} || '/tmp/minion_shared';
    my $setup_dir = "$SHARED/asonnino-hotstuff-redundant";
    make_path($setup_dir) unless -d $setup_dir;

    my $setup_file = "$setup_dir/setup.yaml";
    open(my $fh, '>', $setup_file) or die "Cannot open $setup_file: $!";

    print $fh "interface: \"asonnino-hotstuff-redundant\"\n\n";
    print $fh "parameters:\n";
    printf $fh "  redundancy: %d\n\n", $redundancy;
    print $fh "  client_inflight: 512\n\n";
    print $fh "endpoints:\n\n";
    print $fh "  - addresses:\n";
    foreach my $ip (@ips) {
        print $fh "    - $ip\n";
    }
    print $fh "    tags:\n";
    foreach my $ip (@ips) {
        print $fh "    - $ip\n";
    }
    close($fh);

    return 1;
}

deploy_asonnino_hotstuff_redundant();
__END__
