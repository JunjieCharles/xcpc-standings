import math
import os
import pandas as pd
from opencc import OpenCC
from src.utils.text import normalize_text
from src.utils.school import normalize_school_name

def calcSeed(ratingToCounts, rating, prev=None):
    if prev == None:
        prev = rating
    seed = 1
    for t in ratingToCounts:
        seed += ratingToCounts[t] * (1.0 / (1 + math.pow(10, (rating - t) / 400)))
    seed -= 1.0 / (1 + math.pow(10, (rating - prev) / 400))
    return seed

def calculateRating(userRank, currentRatings):
    '''
    userRank: dict {user:rank}
    currentRatings: dict {user:rating}
    '''
    userCount = len(userRank)
    if userCount == 0:
        return {}
    
    userList = list(userRank.keys())
    ratingToCounts = {}
    
    for user in userList:
        if user not in currentRatings:
            currentRatings[user] = 1400
        rating = currentRatings[user]
        if rating not in ratingToCounts:
            ratingToCounts[rating] = 0
        ratingToCounts[rating] += 1

    delta = {}
    inc_sum = 0
    for user in userList:
        rank = userRank[user]
        rating = currentRatings[user]
        M = math.sqrt(calcSeed(ratingToCounts, rating) * rank)
        l = 1
        r = 8000
        while l < r - 1:
            m = int((l + r) / 2.0)
            if calcSeed(ratingToCounts, m, rating) < M:
                r = m
            else:
                l = m
        delta[user] = int((l - rating) / 2.0)
        inc_sum += delta[user]

    inc = -(inc_sum // userCount) - 1
    for user in delta:
        delta[user] += inc

    userList = sorted(userList, key=lambda x: currentRatings[x], reverse=True)
    
    s = int(min(userCount, 4 * round(math.sqrt(userCount))))
    sum_top = 0
    for i in range(s):
        sum_top += delta[userList[i]]
    
    inc = min(max(-1 * (sum_top // s), -10), 0)
    
    returnValue = {}
    for user in userList:
        rating = currentRatings[user]
        new_rating = rating + delta[user]
        returnValue[user] = new_rating
        
    return returnValue

def normalize(s, t2s=False):
    """Normalize string, with optional Trad-to-Simp conversion."""
    s = str(s)
    s = normalize_text(s)
    if t2s == True or '港' in s or '澳' in s:
        s = OpenCC('t2s').convert(s)
    return s

def rating_color(rating):
    if not rating:
        return 'color:#000000;'
    if rating<1200:
        return 'color:#808080;'
    elif rating<1400:
        return 'color:#008000;'
    elif rating<1600:
        return 'color:#03A89E;'
    elif rating<1900:
        return 'color:#0000FF;'
    elif rating<2100:
        return 'color:#AA00AA;'
    elif rating<2400:
        return 'color:#FFC000;'
    else:
        return 'color:#FF0000;'
