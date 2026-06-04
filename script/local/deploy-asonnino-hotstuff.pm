package deploy_asonnino_hotstuff;

use strict;
use warnings;

my $FLEET = $_;
my %PARAMS = @_;
my $RUNNER = $PARAMS{RUNNER};

my ($action, $redundancy, @err) = @ARGV;
$redundancy //= 1;
my $DEFAULT_CLIENT_INFLIGHT = 4096;
my $DEFAULT_CLIENT_MEMPOOL_MODE = 'round_robin';

sub client_inflight {
    my $value = $ENV{ASONNINO_HOTSTUFF_CLIENT_INFLIGHT};
    if (!defined($value) || $value eq '') {
        return $DEFAULT_CLIENT_INFLIGHT;
    }
    if ($value !~ /^\d+$/ || $value <= 0) {
        die ("invalid ASONNINO_HOTSTUFF_CLIENT_INFLIGHT '$value'");
    }
    return int($value);
}

sub client_mempool_mode {
    my $value = $ENV{ASONNINO_HOTSTUFF_CLIENT_MEMPOOL_MODE};
    if (!defined($value) || $value eq '') {
        return $DEFAULT_CLIENT_MEMPOOL_MODE;
    }
    if ($value ne 'round_robin' && $value ne 'single') {
        die ("invalid ASONNINO_HOTSTUFF_CLIENT_MEMPOOL_MODE '$value'");
    }
    return $value;
}

sub deploy_asonnino_hotstuff {
    my @hotstuff_ips = ();
    foreach my $worker ($FLEET->members()) {
        my $ip = $worker->can('public_ip') ? $worker->public_ip() : $worker->host();
        if ($ip =~ /^10\.30\.10\.\d+$/) {
            push(@hotstuff_ips, $ip);
        }
    }
    
    # Sort IPs by the last octet so the list is stable
    @hotstuff_ips = sort { 
        my ($a_end) = $a =~ /\.([^.]+)$/; 
        my ($b_end) = $b =~ /\.([^.]+)$/; 
        $a_end <=> $b_end 
    } @hotstuff_ips;

    my @workers;
    foreach my $worker ($FLEET->members()) {
        my $ip = $worker->can('public_ip') ? $worker->public_ip() : $worker->host();
        if (grep { $_ eq $ip } @hotstuff_ips) {
            push(@workers, $worker);
        }
    }

    if (scalar(@workers) > 0) {
        my $proc = $RUNNER->run(\@workers, [ 'asonnino-hotstuff', 'deploy' ]);
        if ($proc->wait() != 0) {
            die ("failed to deploy asonnino-hotstuff on remote nodes");
        }
    }

    # Use dedicated setup directory for asonnino-hotstuff.
    my $SHARED = $ENV{MINION_SHARED} || '/tmp/minion_shared';
    my $setup_dir = "$SHARED/asonnino-hotstuff";
    if (!(-d $setup_dir) && !mkdir($setup_dir)) {
        die ("cannot create setup directory '$setup_dir': $!");
    }

    my $setup_file = "$setup_dir/setup.yaml";
    open(my $fh, '>', $setup_file) or die "Cannot open $setup_file: $!";

print $fh "interface: \"asonnino-hotstuff\"\n\n";
print $fh "parameters:\n";
printf $fh "  client_inflight: %d\n", client_inflight();
printf $fh "  client_mempool_mode: %s\n\n", client_mempool_mode();
print $fh "endpoints:\n\n";
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

deploy_asonnino_hotstuff();
__END__
