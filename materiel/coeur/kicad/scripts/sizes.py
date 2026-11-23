import numpy as np, itertools
phi=(1+5**.5)/2
def normals(name):
    if name=='D4': v=np.array([[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1]],float)  # face normals of tetra (dual)
    elif name=='D6': v=np.array([p for p in itertools.product([-1,0,1],repeat=3) if sum(map(abs,p))==1],float)
    elif name=='D8': v=np.array(list(itertools.product([-1,1],repeat=3)),float)
    elif name=='D12': v=np.array([p for c in [(0,1,phi)] for p in set(itertools.permutations((0,1,phi))) ],float)
    elif name=='D20':
        v=[p for p in itertools.product([-1,1],repeat=3)]
        for s1 in [-1,1]:
            for s2 in [-1,1]:
                v+=[(0,s1/phi,s2*phi),(s1/phi,s2*phi,0),(s2*phi,0,s1/phi)]
        v=np.array(v,float)
    elif name=='D10':
        # pentagonal trapezohedron: kite faces, normals tilted; approx standard d10 with tilt ~ 40deg? derive from geometry
        v=[]
        a=np.deg2rad(46.0)  # face normal elevation for common d10 proportions
        for k in range(5):
            th=2*np.pi*k/5; v.append([np.cos(a)*np.cos(th),np.cos(a)*np.sin(th),np.sin(a)])
            th2=th+np.pi/5; v.append([np.cos(a)*np.cos(th2),np.cos(a)*np.sin(th2),-np.sin(a)])
        v=np.array(v)
    if name=='D12':
        vv=[]
        for p in itertools.permutations((0,1,phi)):
            pass
        vv=[]
        for s1 in [-1,1]:
            for s2 in [-1,1]:
                vv+=[(0,s1,s2*phi),(s1,s2*phi,0),(s2*phi,0,s1)]
        v=np.array(vv,float)
    n=v/np.linalg.norm(v,axis=1)[:,None]
    return np.unique(np.round(n,9),axis=0)
def randrot(rng):
    q=rng.normal(size=4);q/=np.linalg.norm(q);w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def min_inradius(n,box,wall=1.6,iters=60000,seed=0):
    rng=np.random.default_rng(seed)
    corners=np.array(list(itertools.product(*[[-d/2,d/2] for d in box])))
    best=1e9
    R=[np.eye(3)]+[randrot(rng) for _ in range(iters)]
    for r in R:
        c=corners@r.T
        need=(c@n.T).max()
        best=min(best,need)
    return best+wall
def size_label(name,r):
    # conventional size: face-to-face (2r) for D6,D8,D12,D20,D10 ; for D4 report edge length and height
    if name=='D4': edge=r*2*np.sqrt(6); return f"arête {edge:.0f} mm, hauteur {4*r:.0f} mm"
    if name=='D6': return f"{2*r:.0f} mm de côté"
    return f"{2*r:.0f} mm face à face"
for label,box in [("Coeur XIAO actuel 21.6x21.6x13.5",(21.6,21.6,13.5)),("Coeur compact (puce nue) 15x15x9",(15,15,9)),("Coeur compact 12 mm rond≈12x12x8",(12,12,8))]:
    print("==",label)
    for d in ['D4','D6','D8','D10','D12','D20']:
        r=min_inradius(normals(d),box,iters=20000)
        print(f"  {d}: {size_label(d,r)}")
