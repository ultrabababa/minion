package behave_asonnino_hotstuff_redundant;

use strict;
use warnings;

use Getopt::Long qw(GetOptionsFromArray);

my $FLEET = $_;
my $MINION_SHARED = $ENV{MINION_SHARED};

my $DATA_DIR = $MINION_SHARED . '/asonnino-hotstuff-redundant';
my $ROLES_PATH = $DATA_DIR . '/behaviors.txt';

my ($number, @err);
my ($worker, $ip, $text, $fh);

GetOptionsFromArray(
    \@ARGV,
    'n|number=i' => \$number
);

@err = @ARGV;
if (@err) {
    die ("unexpected argument '" . shift(@err) . "'");
}

if (!defined($number)) {
    $number = 1;
}

if (!(-d $DATA_DIR) && !mkdir($DATA_DIR)) {
    die ("cannot create data directory: $!");
}

$text = '';
foreach $worker ($FLEET->members()) {
    if ($worker->can('public_ip')) {
        $ip = $worker->public_ip();
    } elsif ($worker->can('host')) {
        $ip = $worker->host();
    } else {
        die ("cannot get ip of worker '$worker'");
    }

    $text .= sprintf("%s:%d\n", $ip, $number);
}

if (!open($fh, '>>', $ROLES_PATH)) {
    die ("cannot open roles file '$ROLES_PATH'");
}

printf($fh "%s", $text);
close($fh);

1;
__END__
