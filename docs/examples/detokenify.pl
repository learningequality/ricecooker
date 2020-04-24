#!/usr/bin/env perl -pi
# multi-line in place substitute
use strict;
use warnings;

BEGIN {undef $/;}

# remove access tokens in case left by mistake
# ####################################################################
s/a5c5fb[\da-f]{34}/YOURTOKENHERE9139139f3a23232/g;
s/70aec3[\da-f]{34}/YOURTOKENHERE9139139f3a23232/g;
s/563554[\da-f]{34}/YOURTOKENHERE9139139f3a23232/g;

