#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Aug 21 20:28:35 2023

@author: green-machine
"""


from stats.src.usa.bea.backend import read_usa_bea_excel

from core.classes import URL, SeriesID
from core.utils import get_kwargs


def main():
    [
        # =====================================================================
        # Fixed Assets Series: K160021, 1951--2011
        # =====================================================================
        # =====================================================================
        # K10002 << K100021 << K160021
        # =====================================================================
        SeriesID("k1n31gd1es00", URL.FIAS)
    ] or [
        # =====================================================================
        # Fixed Assets Series: K10070
        # =====================================================================
        SeriesID("K10070" or "K10002" or "K16002", URL.NIPA)
    ] or [
        # =========================================================
        # U.S. Bureau of Economic Analysis, Produced assets, closing balance: Fixed assets (DISCONTINUED) [K160491A027NBEA], retrieved from FRED, Federal Reserve Bank of St. Louis;
        # https://fred.stlouisfed.org/series/K160491A027NBEA, August 23, 2018.
        # http://www.bea.gov/data/economic-accounts/national
        # https://fred.stlouisfed.org/series/K160491A027NBEA
        # https://search.bea.gov/search?affiliate=u.s.bureauofeconomicanalysis&query=k160491
        # =========================================================
        # =========================================================
        # 'K16049' Replaced with 'K10070' in 'combine_combined_archived()'
        # =========================================================
        SeriesID("K16049", URL.NIPA)
    ]

    # =============================================================================
    # Fixed Assets Series: K160021, 1951--1969
    # =============================================================================
    SERIES_ID = "K160021"
    read_usa_bea_excel(**get_kwargs()).loc[:, [SERIES_ID]]


if __name__ == "__main__":
    main()
