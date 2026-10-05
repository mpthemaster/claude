\ The sieve of Eratosthenes: print the primes below 100.
100 constant n
create sieve n allot          \ one cell per number; 0 means "still possibly prime"

: composite? ( k -- flag )  sieve + @ ;
: strike ( p -- )             \ mark p*p, p*p+p, ... below n as composite
  dup dup * n < if  n over dup * do  1 sieve i + !  dup +loop  then  drop ;
: primes ( -- )
  n 2 do  i composite? 0= if  i .  i strike  then  loop ;

primes cr
