import React, { useState, useEffect, useMemo } from 'react';
import { ChevronLeft, ChevronRight, TrendingUp, TrendingDown, DollarSign, Calendar as CalendarIcon, Save, X, Info, Coins } from 'lucide-react';

const AssetCalendarApp = ({ initialCurrency = 'USD' }) => {
    // --- 설정 및 상수 ---
    const EXCHANGE_RATE = 1450; // 1 USD = 1450 KRW (설정값)

    // --- 상태 관리 ---
    const [currency, setCurrency] = useState(initialCurrency); // 'USD' or 'KRW'
    const [currentDate, setCurrentDate] = useState(new Date());
    const [assetData, setAssetData] = useState({}); // { "YYYY-MM-DD": value (ALWAYS IN USD) }
    const [selectedDate, setSelectedDate] = useState(null);
    const [inputValue, setInputValue] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [hoveredMonthStats, setHoveredMonthStats] = useState(null);
    const [isMockData, setIsMockData] = useState(false);
    const [filledDates, setFilledDates] = useState(new Set()); // Auto-filled dates (holidays)

    // --- 초기 로드 (API Fetch) ---
    useEffect(() => {
        const fetchAssetData = async () => {
            try {
                const marketParam = currency === 'KRW' ? 'kr' : 'us';
                const response = await fetch(`/api/daily-assets?market=${marketParam}`);
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const rawData = await response.json();

                // --- 데이터 전처리 (Gap Filling) ---
                const processedData = { ...rawData };
                const filledIndices = new Set();

                // 날짜 정렬 (오름차순)
                const sortedKeys = Object.keys(rawData).sort();
                if (sortedKeys.length > 0) {
                    const startDate = new Date(sortedKeys[0]);
                    const today = new Date();
                    // 오늘날짜까지만 채움 (미래 날짜 제외)

                    let currentDateIterator = new Date(startDate);
                    let lastValue = rawData[sortedKeys[0]];

                    while (currentDateIterator <= today) {
                        const dateKey = currentDateIterator.toISOString().split('T')[0];

                        if (processedData[dateKey] !== undefined) {
                            lastValue = processedData[dateKey];
                        } else {
                            // 데이터가 비어있으면 이전 값으로 채움
                            processedData[dateKey] = lastValue;
                            filledIndices.add(dateKey);
                        }

                        currentDateIterator.setDate(currentDateIterator.getDate() + 1);
                    }
                }

                setAssetData(processedData);
                setFilledDates(filledIndices);
                setIsMockData(false);
            } catch (error) {
                console.error("데이터 로딩 실패:", error);
                // 에러 발생 시 빈 객체 혹은 기존 데이터 유지 (혹은 사용자 알림)
            }
        };

        fetchAssetData();
    }, [currency]); // currency가 바뀔 때마다 다시 fetch

    // --- 데이터 저장 (수정 불가) ---
    const saveAssetData = (newData) => {
        // API 연동 모드에서는 클라이언트 사이드 저장을 비활성화합니다.
        // 추후 서버 API에 POST 요청을 보내는 것으로 대체 가능
        setAssetData(newData);
        console.warn("Client-side save is disabled in API mode.");
    };

    // --- 헬퍼 함수: 금액 포맷팅 (핵심) ---
    const formatMoney = (usdValue, showSymbol = true) => {
        if (usdValue === undefined || usdValue === null) return '-';

        let val = usdValue;
        let symbol = '$';

        if (currency === 'KRW') {
            val = usdValue * EXCHANGE_RATE;
            symbol = '₩';
        }

        // 소수점 처리: 달러는 정수, 원화도 정수 (필요시 toFixed 조정)
        const formattedNum = Math.round(val).toLocaleString();
        return showSymbol ? `${symbol}${formattedNum}` : formattedNum;
    };

    const formatAbbreviatedMoney = (usdValue) => {
        if (usdValue === undefined || usdValue === null) return '';

        let val = usdValue;

        if (currency === 'KRW') {
            val = usdValue * EXCHANGE_RATE;
            const absVal = Math.abs(val);
            const sign = val < 0 ? '-' : '';

            // 억 단위 (100,000,000)
            if (absVal >= 100_000_000) {
                let ok = Math.floor(absVal / 100_000_000);
                let man = Math.round((absVal % 100_000_000) / 10_000);

                if (man >= 10000) {
                    ok += 1;
                    man = 0;
                }

                return `${sign}${ok}억${man > 0 ? `${man}만` : ''}원`;
            }
            // 만 단위 (10,000)
            if (absVal >= 10_000) {
                const man = Math.round(absVal / 10_000);
                return `${sign}${man}만원`;
            }

            return `${sign}${Math.round(absVal).toLocaleString()}원`;
        } else {
            // USD
            const absVal = Math.abs(val);
            const sign = val < 0 ? '-' : '';

            if (absVal >= 1_000_000_000) {
                return `${sign}$${(absVal / 1_000_000_000).toFixed(2)}B`;
            }
            if (absVal >= 1_000_000) {
                return `${sign}$${(absVal / 1_000_000).toFixed(2)}M`;
            }
            if (absVal >= 1_000) {
                return `${sign}$${(absVal / 1_000).toFixed(2)}K`;
            }
            return `${sign}$${absVal.toLocaleString()}`;
        }
    };

    // --- 날짜 도우미 함수 ---
    const formatDateKey = (date) => date.toISOString().split('T')[0];
    const getPreviousDateKey = (dateKey) => {
        const date = new Date(dateKey);
        date.setDate(date.getDate() - 1);
        return formatDateKey(date);
    };

    const formatDisplayDate = (date) => {
        return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
    };

    // --- 5주 뷰 계산 함수 ---
    const getViewRange = () => {
        const dayOfWeek = currentDate.getDay(); // 0 (Sun) ~ 6 (Sat)
        // 현재 날짜가 포함된 주의 '토요일'을 endDay로 설정
        const endDay = new Date(currentDate);
        endDay.setDate(currentDate.getDate() + (6 - dayOfWeek));

        // 5주 전 시작일 계산 (EndDay - 34일)
        const startDay = new Date(endDay);
        startDay.setDate(endDay.getDate() - 34);
        return { startDay, endDay };
    };

    // --- 이벤트 핸들러 ---
    const handlePrevWeek = () => {
        const newDate = new Date(currentDate);
        newDate.setDate(newDate.getDate() - 7);
        setCurrentDate(newDate);
    };

    const handleNextWeek = () => {
        const newDate = new Date(currentDate);
        newDate.setDate(newDate.getDate() + 7);
        setCurrentDate(newDate);
    };

    const handleDateClick = (dateStr) => {
        setSelectedDate(dateStr);
        // 입력창 초기값 설정: 저장된 USD 값을 현재 통화에 맞춰 변환해서 보여줌
        const usdVal = assetData[dateStr];
        if (usdVal !== undefined) {
            const displayVal = currency === 'KRW' ? Math.round(usdVal * EXCHANGE_RATE) : usdVal;
            setInputValue(displayVal);
        } else {
            setInputValue('');
        }
        setIsModalOpen(true);
    };

    const handleSaveInput = (e) => {
        e.preventDefault();
        if (!selectedDate) return;

        // 입력된 값을 숫자로 변환 (콤마 제거)
        const rawVal = parseInt(inputValue.toString().replace(/,/g, ''), 10);
        const newData = { ...assetData };

        if (isNaN(rawVal)) {
            delete newData[selectedDate];
        } else {
            // 저장 시: 현재 입력된 값이 KRW라면 USD로 역환산하여 저장
            let usdToSave = rawVal;
            if (currency === 'KRW') {
                usdToSave = Math.round(rawVal / EXCHANGE_RATE);
            }
            newData[selectedDate] = usdToSave;
        }

        saveAssetData(newData);
        setIsModalOpen(false);
    };
    const closeModal = () => setIsModalOpen(false);

    // --- 헬퍼 함수: 퍼센트에 따른 색상 반환 (4단계 구간) ---
    const getColorClass = (percent, isTextOnly = false) => {
        if (percent >= 20) return isTextOnly ? 'text-green-600' : { bg: 'bg-green-300', text: 'text-green-950', border: 'border-green-400' };
        if (percent >= 10) return isTextOnly ? 'text-green-600' : { bg: 'bg-green-200', text: 'text-green-900', border: 'border-green-300' };
        if (percent >= 3) return isTextOnly ? 'text-green-600' : { bg: 'bg-green-100', text: 'text-green-800', border: 'border-green-200' };
        if (percent > 0) return isTextOnly ? 'text-green-600' : { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-100' };

        if (percent <= -20) return isTextOnly ? 'text-red-600' : { bg: 'bg-red-300', text: 'text-red-950', border: 'border-red-400' };
        if (percent <= -10) return isTextOnly ? 'text-red-600' : { bg: 'bg-red-200', text: 'text-red-900', border: 'border-red-300' };
        if (percent <= -3) return isTextOnly ? 'text-red-600' : { bg: 'bg-red-100', text: 'text-red-800', border: 'border-red-200' };
        if (percent < 0) return isTextOnly ? 'text-red-600' : { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-100' };

        return isTextOnly ? 'text-gray-400' : { bg: 'bg-white', text: 'text-gray-400', border: 'border-gray-200' };
    };

    // --- 미니 차트용 색상 (배경만 필요) ---
    const getChartColorClass = (percent) => {
        if (percent >= 10) return 'bg-green-500';
        if (percent >= 5) return 'bg-green-400';
        if (percent > 0) return 'bg-green-300';
        if (percent === 0) return 'bg-gray-200';
        if (percent > -5) return 'bg-red-300';
        if (percent > -10) return 'bg-red-400';
        return 'bg-red-500';
    };

    // --- 렌더링 헬퍼 ---
    const renderCalendarCells = () => {
        const { startDay } = getViewRange();
        const cells = [];

        for (let i = 0; i < 35; i++) {
            const date = new Date(startDay);
            date.setDate(startDay.getDate() + i);

            const key = formatDateKey(date);
            const prevKey = getPreviousDateKey(key);
            const currentValue = assetData[key];
            const prevValue = assetData[prevKey];

            let percentChange = 0;
            let diffValue = 0; // 항상 USD 기준 차이값 저장 (표시할때만 변환)
            let hasChange = false;

            if (currentValue !== undefined && prevValue !== undefined && prevValue !== 0) {
                diffValue = currentValue - prevValue;
                percentChange = parseFloat(((diffValue / prevValue) * 100).toFixed(2));
                hasChange = true;
            }

            const isToday = key === formatDateKey(new Date());
            const { bg, text, border } = hasChange ? getColorClass(percentChange) : getColorClass(0);
            const cellBgClass = hasChange ? bg : (isToday ? 'bg-amber-50' : 'bg-white');

            cells.push(
                <div
                    key={key}
                    onClick={() => handleDateClick(key)}
                    className={`h-16 md:h-20 relative cursor-pointer transition-all hover:bg-opacity-90 ${cellBgClass} group ${isToday ? 'ring-2 ring-inset ring-amber-400 z-10' : ''}`}
                >
                    <div className="absolute top-1 left-2 flex items-baseline gap-1 z-10">
                        <span className={`text-[10px] font-medium ${isToday ? 'text-amber-600 font-bold' : 'text-gray-500'}`}>
                            {date.getMonth() + 1}/{date.getDate()}
                        </span>
                        {/* 휴일/Filled 표시 (옵션) - 지금은 숨김 */}
                    </div>

                    {/* Center: Percent Change Only (High Contrast, Large Text) */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none p-1">
                        {/* filledDates에 포함되면 변동률 숨김 */}
                        {!filledDates.has(key) && hasChange ? (
                            <span className={`text-2xl md:text-3xl font-black tracking-tighter leading-none ${text} drop-shadow-sm scale-110`}>
                                {percentChange > 0 ? '+' : ''}{percentChange.toFixed(2)}%
                            </span>
                        ) : currentValue !== undefined && !filledDates.has(key) ? (
                            <span className="text-gray-300 text-sm font-bold">-</span>
                        ) : (
                            // Filled date or no value
                            <span className="opacity-0 group-hover:opacity-100 text-gray-300 text-base font-light transition-opacity">+</span>
                        )}
                    </div>

                    {/* Bottom Right: Change Amount & Total Value */}
                    {currentValue !== undefined && (
                        <div className="absolute bottom-1 right-2 text-right flex flex-col items-end justify-end pointer-events-none gap-px">
                            {/* filledDates에 포함되면 변동액 숨김 */}
                            {!filledDates.has(key) && hasChange && (
                                <span className={`text-[8px] md:text-[9px] font-bold tabular-nums leading-none ${text} opacity-90`}>
                                    {diffValue > 0 ? '+' : diffValue < 0 ? '-' : ''}{formatMoney(Math.abs(diffValue), true)}
                                </span>
                            )}
                            <span className={`text-[8px] md:text-[9px] font-semibold tracking-tight tabular-nums leading-none ${filledDates.has(key) ? 'text-gray-300' : 'text-gray-400'}`}>
                                {formatMoney(currentValue, true)}
                            </span>
                            <span className={`text-[7px] md:text-[8px] font-medium tracking-tighter leading-none mt-0.5 ${filledDates.has(key) ? 'text-gray-300/60' : 'text-gray-400/80'}`}>
                                {formatAbbreviatedMoney(currentValue)}
                            </span>
                        </div>
                    )}
                </div>
            );
        }
        return cells;
    };

    // --- 데이터 계산 (useMemo) ---
    const rangeStats = useMemo(() => {
        const { startDay, endDay } = getViewRange();

        const keysInView = [];
        for (let i = 0; i < 35; i++) {
            const d = new Date(startDay);
            d.setDate(startDay.getDate() + i);
            const k = formatDateKey(d);
            if (assetData[k] !== undefined) keysInView.push(k);
        }

        if (keysInView.length === 0) return null;

        const firstKey = keysInView[0];
        const lastKey = keysInView[keysInView.length - 1];

        const startVal = assetData[firstKey];
        const endVal = assetData[lastKey];
        const diff = endVal - startVal;
        const rate = startVal !== 0 ? ((diff / startVal) * 100).toFixed(2) : 0;

        return { startVal, endVal, diff, rate, firstDate: firstKey, lastDate: lastKey, startDayObj: new Date(firstKey), endDayObj: new Date(lastKey) };
    }, [assetData, currentDate]);

    const yoyStats = useMemo(() => {
        if (!rangeStats) return null;

        const oneYearAgoStart = new Date(rangeStats.startDayObj);
        oneYearAgoStart.setFullYear(oneYearAgoStart.getFullYear() - 1);

        const oneYearAgoEnd = new Date(rangeStats.endDayObj);
        oneYearAgoEnd.setFullYear(oneYearAgoEnd.getFullYear() - 1);

        const findClosestVal = (targetDate) => {
            const key = formatDateKey(targetDate);
            if (assetData[key]) return assetData[key];
            for (let i = 1; i <= 3; i++) {
                const prev = new Date(targetDate); prev.setDate(targetDate.getDate() - i);
                const prevKey = formatDateKey(prev);
                if (assetData[prevKey]) return assetData[prevKey];
                const next = new Date(targetDate); next.setDate(targetDate.getDate() + i);
                const nextKey = formatDateKey(next);
                if (assetData[nextKey]) return assetData[nextKey];
            }
            return null;
        };

        const startValYoY = findClosestVal(oneYearAgoStart);
        const endValYoY = findClosestVal(oneYearAgoEnd);

        if (startValYoY === null || endValYoY === null) return null;

        const diffYoY = endValYoY - startValYoY;
        const rateYoY = startValYoY !== 0 ? ((diffYoY / startValYoY) * 100).toFixed(2) : 0;

        return { rate: rateYoY, diff: diffYoY };
    }, [assetData, rangeStats]);

    const monthlyHistory = useMemo(() => {
        const history = [];
        const baseDate = rangeStats ? rangeStats.endDayObj : new Date();

        for (let i = 11; i >= 0; i--) {
            const targetDate = new Date(baseDate.getFullYear(), baseDate.getMonth() - i, 1);
            const year = targetDate.getFullYear();
            const month = targetDate.getMonth();

            const keysInMonth = Object.keys(assetData).filter(k => {
                const d = new Date(k);
                return d.getFullYear() === year && d.getMonth() === month;
            }).sort();

            if (keysInMonth.length < 2) {
                history.push({ year, month, rate: null, label: targetDate.toLocaleString('default', { month: 'short' }) });
                continue;
            }

            const startVal = assetData[keysInMonth[0]];
            const endVal = assetData[keysInMonth[keysInMonth.length - 1]];
            const rate = startVal !== 0 ? ((endVal - startVal) / startVal) * 100 : 0;

            history.push({
                year,
                month,
                rate: parseFloat(rate.toFixed(2)),
                label: targetDate.toLocaleString('en-US', { month: 'narrow' })
            });
        }
        return history;
    }, [assetData, rangeStats]);

    const { startDay, endDay } = getViewRange();

    return (
        <div className="bg-gray-50 text-gray-800 font-sans text-sm">
            <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-10 box-border">
                <div className="max-w-5xl mx-auto px-3 py-2 flex justify-between items-center gap-2">

                    <div className="flex items-center gap-2">
                        {/* Mock Data Indicator */}
                        {isMockData && (
                            <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 text-[10px] font-bold border border-amber-200">
                                MOCK DATA
                            </span>
                        )}
                    </div>

                    <div className="flex items-center bg-gray-100 rounded-md p-0.5 shadow-inner">
                        <button onClick={handlePrevWeek} className="p-1 hover:bg-white rounded shadow-sm transition-all text-gray-600 active:scale-95">
                            <ChevronLeft className="w-3.5 h-3.5" />
                        </button>
                        <div className="px-3 text-center">
                            <span className="text-xs font-bold text-gray-700 tracking-wide block">
                                {formatDisplayDate(startDay)} ~ {formatDisplayDate(endDay)}
                            </span>
                        </div>
                        <button onClick={handleNextWeek} className="p-1 hover:bg-white rounded shadow-sm transition-all text-gray-600 active:scale-95">
                            <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div >
            </header >

            <main className="max-w-5xl mx-auto px-2 py-3">
                {/* 요약 카드 */}
                {rangeStats && (
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-3 mb-3 grid grid-cols-1 md:grid-cols-[auto_1fr_auto] gap-4 items-center">

                        {/* 1. Start / End 정보 (왼쪽) */}
                        <div className="flex gap-3 justify-between md:justify-start min-w-[140px]">
                            <div className="flex flex-col">
                                <span className="text-[10px] text-gray-400 font-medium mb-0.5 tracking-wide uppercase">Start</span>
                                <span className="text-xs font-semibold text-gray-500 mb-px">{rangeStats.firstDate.replace(/-/g, '.')}</span>
                                <span className="text-base font-bold text-gray-700 leading-none">{formatMoney(rangeStats.startVal)}</span>
                            </div>
                            <div className="w-px bg-gray-100 h-auto self-stretch"></div>
                            <div className="flex flex-col">
                                <span className="text-[10px] text-gray-400 font-medium mb-0.5 tracking-wide uppercase">End</span>
                                <span className="text-xs font-semibold text-gray-500 mb-px">{rangeStats.lastDate.replace(/-/g, '.')}</span>
                                <span className="text-base font-bold text-gray-800 leading-none">{formatMoney(rangeStats.endVal)}</span>
                            </div>
                        </div>

                        {/* 2. 12개월 월별 수익률 (가운데) */}
                        <div className="flex flex-col items-center justify-center w-full px-2 border-t border-b border-gray-100 md:border-0 py-2 md:py-0">
                            <div className="flex items-center gap-1.5 mb-1">
                                <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Past 12 Months</span>
                                {hoveredMonthStats && (
                                    <span className={`text-[9px] font-bold ml-2 ${hoveredMonthStats.rate > 0 ? 'text-green-600' : hoveredMonthStats.rate < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                                        {hoveredMonthStats.year}.{hoveredMonthStats.month + 1}: {hoveredMonthStats.rate > 0 ? '+' : ''}{hoveredMonthStats.rate}%
                                    </span>
                                )}
                            </div>
                            <div className="flex gap-0.5 w-full max-w-[280px] justify-between h-5">
                                {monthlyHistory.map((m, idx) => (
                                    <div
                                        key={idx}
                                        className={`
                                        flex-1 rounded-[1px] relative group cursor-help transition-all hover:scale-110 hover:z-10
                                        flex items-center justify-center
                                        ${m.rate !== null ? getChartColorClass(m.rate) : 'bg-gray-100'}
                                        `}
                                        onMouseEnter={() => setHoveredMonthStats(m)}
                                        onMouseLeave={() => setHoveredMonthStats(null)}
                                    >
                                        {/* removed text label inside tiny bars for compactness */}
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* 3. YoY & Period Return (오른쪽) */}
                        <div className="flex gap-4 justify-end items-start">
                            {/* YoY Block */}
                            {yoyStats && (
                                <div className="flex flex-col items-end opacity-60 hover:opacity-100 transition-opacity cursor-default group h-full justify-between">
                                    <div className="flex items-center gap-1 mb-px h-[12px]">
                                        <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wide leading-none">Return</span>
                                        <span className="text-[8px] font-semibold text-gray-400 uppercase tracking-wide leading-none mt-px">(1Y Ago)</span>
                                        <Info className="w-2.5 h-2.5 text-gray-300 hidden group-hover:block" />
                                    </div>
                                    <span className={`font-bold text-base leading-none ${yoyStats.rate > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {yoyStats.rate > 0 ? '+' : ''}{yoyStats.rate}%
                                    </span>
                                </div>
                            )}

                            {/* Period Return Block */}
                            <div className="flex items-center gap-2">
                                <div className={`flex flex-col items-end h-full justify-between`}>
                                    <div className="flex items-center gap-1 mb-px h-[12px]">
                                        <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wide leading-none">Return</span>
                                    </div>
                                    <span className={`font-bold text-lg leading-none ${rangeStats.diff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {rangeStats.diff > 0 ? '+' : ''}{rangeStats.rate}%
                                    </span>
                                </div>
                                <div className={`p-1.5 rounded-full ${rangeStats.diff >= 0 ? 'bg-green-50' : 'bg-red-50'}`}>
                                    {rangeStats.diff >= 0 ? <TrendingUp className="w-4 h-4 text-green-500" /> : <TrendingDown className="w-4 h-4 text-red-500" />}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* 색상 범례 (Legend) */}
                <div className="flex rounded overflow-hidden text-[8px] font-medium border border-gray-200 shadow-sm max-w-sm mx-auto mb-2 tracking-tight">
                    <div className="bg-red-300 text-red-950 flex-1 py-1 text-center flex justify-center items-center" title="20% 이상 하락">&lt;-20%</div>
                    <div className="bg-red-200 text-red-900 flex-1 py-1 text-center flex justify-center items-center" title="10% ~ 20% 하락">-20~-10</div>
                    <div className="bg-red-100 text-red-800 flex-1 py-1 text-center flex justify-center items-center" title="3% ~ 10% 하락">-10~-3</div>
                    <div className="bg-red-50 text-red-600 flex-1 py-1 text-center flex justify-center items-center" title="0% ~ 3% 하락">-3~0%</div>
                    <div className="bg-green-50 text-green-600 flex-1 py-1 text-center flex justify-center items-center" title="0% ~ 3% 상승">0~+3%</div>
                    <div className="bg-green-100 text-green-800 flex-1 py-1 text-center flex justify-center items-center" title="3% ~ 10% 상승">+3~+10</div>
                    <div className="bg-green-200 text-green-900 flex-1 py-1 text-center flex justify-center items-center" title="10% ~ 20% 상승">+10~+20</div>
                    <div className="bg-green-300 text-green-950 flex-1 py-1 text-center flex justify-center items-center" title="20% 이상 상승">&gt;+20%</div>
                </div>

                {/* 캘린더 그리드 (5주 뷰) */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="grid grid-cols-7 bg-gray-300 gap-px border-b border-gray-300">
                        {['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'].map((day, i) => (
                            <div key={day} className={`bg-gray-50/80 py-1.5 text-center text-[9px] font-bold tracking-wider ${i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-400' : 'text-gray-400'}`}>{day}</div>
                        ))}
                    </div>
                    <div className="grid grid-cols-7 gap-px bg-gray-300">
                        {renderCalendarCells()}
                    </div>
                </div>
            </main>

            {/* 입력 모달 */}
            {
                isModalOpen && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
                        <div className="bg-white rounded-xl shadow-2xl w-full max-w-xs p-5 transform transition-all scale-100">
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="text-base font-bold text-gray-800 flex items-center gap-2"><CalendarIcon className="w-4 h-4 text-blue-600" /> {selectedDate}</h3>
                                <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
                            </div>
                            <form onSubmit={handleSaveInput}>
                                <div className="mb-4">
                                    <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wide">Total Assets ({currency})</label>
                                    <div className="relative">
                                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                            {currency === 'USD' ? <DollarSign className="w-4 h-4 text-gray-400" /> : <span className="text-gray-400 font-bold text-sm">₩</span>}
                                        </div>
                                        <input type="text" className="block w-full pl-9 pr-3 py-2.5 border-gray-200 border rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none text-lg font-bold tabular-nums text-gray-800 placeholder-gray-300 transition-all" placeholder="0" value={typeof inputValue === 'number' ? inputValue.toLocaleString() : inputValue} onChange={(e) => { const rawVal = e.target.value.replace(/,/g, ''); if (!isNaN(rawVal)) setInputValue(rawVal); }} autoFocus />
                                    </div>
                                </div>
                                <div className="flex gap-2">
                                    <button type="button" onClick={closeModal} className="flex-1 px-3 py-2.5 bg-white border border-gray-200 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">Cancel</button>
                                    <button type="submit" className="flex-1 px-3 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 shadow-sm transition-colors flex justify-center items-center gap-1.5"><Save className="w-3.5 h-3.5" />Save</button>
                                </div>
                            </form>
                        </div>
                    </div>
                )
            }
        </div >
    );
};

export default AssetCalendarApp;
