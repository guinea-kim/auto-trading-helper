import React from 'react';
import { createRoot } from 'react-dom/client';
import AssetCalendarApp from './AssetCalendarApp';

const container = document.getElementById('react-root');
if (container) {
    const params = new URLSearchParams(window.location.search);
    const market = params.get('market');
    const currency = (market === 'kr-calendar') ? 'KRW' : 'USD';

    const root = createRoot(container);
    root.render(<AssetCalendarApp initialCurrency={currency} />);
}
