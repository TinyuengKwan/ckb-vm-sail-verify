/* Backend-generation smoke only: not the CKB-VM ADD model or a proof. */
default Order dec
$include <prelude.sail>
val add_words : (bits(64), bits(64)) -> bits(64)
function add_words (x, y) = x + y
