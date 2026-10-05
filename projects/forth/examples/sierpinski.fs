\ Draw Sierpinski's triangle as an SVG: square (x, y) is filled when
\ x and y share no 1 bits, which is Pascal's triangle taken mod 2.
64 constant size  8 constant px

: q ( -- ) [char] " emit ;                 \ a double quote
: n. ( n -- ) 0 .r ;                       \ a number, no trailing space
: filled? ( x y -- flag ) and 0= ;
: square ( x y -- )  ." M" swap px * n. space px * n. ." h" px n. ." v" px n. ." h-" px n. ." z" ;
: svg ( -- )
  ." <svg xmlns=" q ." http://www.w3.org/2000/svg" q
  ."  viewBox=" q ." 0 0 " size px * n. space size px * n. q ." >" cr
  ." <path fill=" q ." #4a6fa5" q ."  d=" q
  size 0 do  size 0 do  i j filled? if i j square then  loop  cr  loop
  q ." />" cr ." </svg>" cr ;

svg
