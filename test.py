from operator import *
from drython.macro import *
from drython.core import *
from drython.statement import *
from drython.s_expression import S

expensive_get_number = lambda: do(Print("spam"),14)

# triple_1 = S(L1, S.n,
#              +S(sum,S(entuple,~S.n,~S.n,~S.n)),
#              )
#
# triple_1 = S(fn, [S.n],[],0,0,
#              +S(sum,S(entuple,~S.n,~S.n,~S.n)),
#              )
#
# mtriple1 = macro(triple_1())

# triple_1 = macro(S(s_eval,triple_1)())

# triple_1 = S(mac, [S.n],[],0,0,
#              +S(sum,S(entuple,~S.n,~S.n,~S.n)))()

# S(defmac, S.triple_1, [S.n],[],0,0,
#     +S(sum,S(entuple,~S.n,~S.n,~S.n))).s_eval(globals())

triple_2 = \
  S(defmac, S.triple_2, [S.n],[],0,0,
  S(let_n, (S.g_n, S(gensym, 'g_n')),
    # S(Print,S(scope)),
    +S(do,
       S(setq, ~S.g_n, ~S.n),
       S(sum,S(entuple,~S.g_n,~S.g_n,~S.g_n)))))()


# expanded1 = triple_1(S.expensive_get_number)
#
# print(S(S.triple_1, S(S.expensive_get_number)).s_eval(globals()))

# triple_2 = S(defmac_g_, S.triple_2, [S.n],[],None,False,
#                   S(sum,S(entuple,~S.g_n,~S.g_n,~S.g_n)))()


Print(triple_2(S(S.foo)))
Print(triple_2(S(expensive_get_number))())
# Print(S(triple_2,1)())
# Print(S(triple_2,S(expensive_get_number))())
