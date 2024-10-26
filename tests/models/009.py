def res():
    return a+b-c/d

a=10
b=20
c=8
d=2
def work():
    return Box(res(), 1, 1, align=(Align.MIN,) * 3)
