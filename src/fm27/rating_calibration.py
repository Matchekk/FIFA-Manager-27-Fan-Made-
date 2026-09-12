"""Monotonic FM-scale calibration; level values themselves always come from native code."""
import bisect
import hashlib

FAMILIES={
    'GK':'GK','CB':'CB','SW':'CB','LB':'FULLBACK','RB':'FULLBACK','LWB':'FULLBACK','RWB':'FULLBACK',
    'DM':'MIDFIELD','CDM':'MIDFIELD','ANC':'MIDFIELD','CM':'MIDFIELD',
    'AM':'ATTACKING_MIDFIELD','CAM':'ATTACKING_MIDFIELD',
    'LM':'WIDE','RM':'WIDE','LW':'WIDE','RW':'WIDE','ST':'FORWARD','CF':'FORWARD',
}

def family(position):
    if position not in FAMILIES: raise ValueError('Unsupported rating position')
    return FAMILIES[position]


def holdout(fifa_id):
    if not str(fifa_id).isdigit() or int(fifa_id)<=0: raise ValueError('Positive FIFA identity required')
    return int(hashlib.sha256(('fm27-rating-v1:'+str(fifa_id)).encode()).hexdigest(),16)%5==0


def quantile(values,fraction):
    if not values or not 0<=fraction<=1: raise ValueError('Invalid quantile input')
    ordered=sorted(values)
    offset=(len(ordered)-1)*fraction
    lower=int(offset)
    upper=min(lower+1,len(ordered)-1)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(offset-lower)


def fit_native_scale(pairs):
    """Match robust distribution anchors, not individual historical ratings."""
    if len(pairs)<100: raise ValueError('Insufficient independent positional calibration sample')
    if any(not 0<=x<=99 or not 0<=y<=99 for x,y in pairs): raise ValueError('Invalid native level')
    source,destination=zip(*pairs)
    by_x={}
    for q in (.10,.25,.50,.75,.90,.95):
        x,y=quantile(source,q),quantile(destination,q)
        by_x.setdefault(x,[]).append(y)
    anchors=[(x,sum(ys)/len(ys)) for x,ys in sorted(by_x.items())]
    if len(anchors)<2: raise ValueError('Calibration sample has no useful level range')
    return dict(anchors=anchors,training_players=len(pairs),maximum_level_correction=8,
        minimum_tail_slope=.5,maximum_tail_slope=1.5)


def calibrated_level(model,level):
    if not 0<=level<=99: raise ValueError('Invalid native level')
    anchors=model['anchors']
    index=bisect.bisect_right([p[0] for p in anchors],level)-1
    extrapolated=index<0 or index>=len(anchors)-1
    index=max(0,min(index,len(anchors)-2))
    x0,y0=anchors[index]; x1,y1=anchors[index+1]
    slope=(y1-y0)/(x1-x0)
    if extrapolated: slope=max(model['minimum_tail_slope'],min(model['maximum_tail_slope'],slope))
    mapped=(y1+(level-x1)*slope) if level>=anchors[-1][0] else y0+(level-x0)*slope
    limit=model['maximum_level_correction']
    return max(0,min(99,max(level-limit,min(level+limit,mapped))))


def attributes_for_variant(before,source,percent,offset,cap=20):
    """Materialize a variant whose FM-level has already been evaluated natively."""
    if set(before)!=set(source) or percent not in (50,75,100) or not -8<=offset<=8 or cap!=20:
        raise ValueError('Unsupported native calibration grid variant')
    result={}
    for field,old in before.items():
        new=source[field]
        if type(old) is not int or type(new) is not int or not 0<=old<=99 or not 0<=new<=99:
            raise ValueError('Invalid attribute value')
        result[field]=old if old==new else max(0,old-cap,min(99,old+cap,(old*(100-percent)+new*percent+50)//100+offset))
    return result
