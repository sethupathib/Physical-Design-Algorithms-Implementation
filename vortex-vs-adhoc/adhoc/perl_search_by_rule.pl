#!/usr/bin/env perl
# Ad-hoc Perl equivalent of policy/design_health.yaml (7 rules).
# Same procedural shape as Bash — patterns and thresholds live in code.
use strict;
use warnings;
use JSON::PP;

my $log = shift @ARGV or die "Usage: $0 <logfile>\n";
open my $fh, '<', $log or die "cannot open $log: $!";
my @lines = <$fh>;
close $fh;

my @rules = (
  { name => 'setup_violation', severity => 'error',
    pattern => qr/VIOLATED.*\bsetup\b|Setup\s+slack\s+-\d/i, threshold => 0,
    note => 'Timing setup fails (any count is actionable).' },
  { name => 'hold_violation', severity => 'error',
    pattern => qr/VIOLATED.*\bhold\b|Hold\s+slack\s+-\d/i, threshold => 0,
    note => 'Timing hold fails.' },
  { name => 'max_transition', severity => 'warning',
    pattern => qr/max_transition|MaxTran|MAXTRAN/i, threshold => 10,
    note => 'Flag only if more than 10 MaxTran hits (noise floor).' },
  { name => 'drc_error', severity => 'error',
    pattern => qr/\bDRC\b.*(error|violation|fail)|ERROR:\s*DRC/i, threshold => 0,
    note => 'Hard DRC errors.' },
  { name => 'antenna', severity => 'warning',
    pattern => qr/\bANTENNA\b|antenna\s+violation/i, threshold => 5,
    note => 'Antenna noise below 5 is ignored.' },
  { name => 'congestion_hotspot', severity => 'warning',
    pattern => qr/Congestion\s*>\s*0\.(8|9)|Overflow\s*>\s*[5-9]\d/i, threshold => 0,
    note => 'Routing congestion / overflow hotspots.' },
  { name => 'fatal_or_abort', severity => 'fatal',
    pattern => qr/\bFATAL\b|\bABORT\b|stack\s+trace|INTERNAL\s+ERROR/i, threshold => 0,
    note => 'Tool death / internal errors — stop and escalate.' },
);

my @results;
print "# perl ad-hoc report  log=$log\n# engine=perl_adhoc_procedural\n\n";

for my $r (@rules) {
  my $count = 0;
  my ($first_ln, $first_txt) = (0, '');
  for my $i (0 .. $#lines) {
    if ($lines[$i] =~ $r->{pattern}) {
      $count++;
      if ($count == 1) {
        $first_ln = $i + 1;
        $first_txt = $lines[$i];
        chomp $first_txt;
      }
    }
  }
  my $triggered = $count > $r->{threshold} ? 1 : 0;
  my $flag = $triggered ? 'TRIGGERED' : 'ok';
  printf "[%-7s] %-22s count=%5d thr=%s  %s\n",
    $r->{severity}, $r->{name}, $count, $r->{threshold}, $flag;
  if ($triggered) {
    my $snip = substr($first_txt, 0, 100);
    print "           first \@$first_ln: $snip\n";
  }
  push @results, {
    name => $r->{name},
    severity => $r->{severity},
    count => $count + 0,
    threshold => $r->{threshold} + 0,
    triggered => $triggered ? JSON::PP::true : JSON::PP::false,
  };
}

my $out = $ENV{OUT_DIR} ? "$ENV{OUT_DIR}/perl_report.json" : "perl_report.json";
open my $jf, '>', $out or die $!;
print $jf JSON::PP->new->pretty->encode({
  engine => 'perl_adhoc_procedural',
  log => $log,
  results => \@results,
});
close $jf;
