#!/usr/bin/env perl -pi
# multi-line in place substitute
use strict;
use warnings;

BEGIN {undef $/;}

# remove tokens and emails substitutions
# ####################################################################
s/70aec3[\da-f]{34}/YOURTOKENHERE9139139f3a23232/g;
s/ivan.savov\@gmail.com/you\@yourdomain.org/g;
