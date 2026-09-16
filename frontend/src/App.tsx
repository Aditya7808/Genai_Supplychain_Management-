import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { DashboardView } from './views/DashboardView';
import { ChatView } from './views/ChatView';
import { ForecastView } from './views/ForecastView';
import { TransfersView } from './views/TransfersView';
import { WhatIfView } from './views/WhatIfView';
import { ApprovalsView } from './views/ApprovalsView';
import { fetchHealth, fetchApprovals, fetchReplenishmentAlerts } from './api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isHealthy, setIsHealthy] = useState(true);
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);
  const [alertCount, setAlertCount] = useState(0);

  // Context passed between tabs (e.g. from Dashboard click into Forecast or Chat)
  const [navContext, setNavContext] = useState<{ skuId?: string; warehouseId?: string }>({
    skuId: 'SKU_001',
    warehouseId: 'WH_01',
  });

  const checkStatus = async () => {
    try {
      const h = await fetchHealth();
      setIsHealthy(h.status === 'ok');

      const [apps, alerts] = await Promise.all([
        fetchApprovals('pending'),
        fetchReplenishmentAlerts(10),
      ]);
      setPendingApprovalsCount(apps.length);
      setAlertCount(alerts.filter((a) => a.status === 'CRITICAL').length);
    } catch {
      setIsHealthy(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 20000);
    return () => clearInterval(interval);
  }, []);

  const handleNavigate = (tab: string, context?: { skuId?: string; warehouseId?: string }) => {
    if (context) {
      setNavContext(context);
    }
    setActiveTab(tab);
  };

  const getPageMeta = () => {
    switch (activeTab) {
      case 'dashboard':
        return {
          title: 'Supply Chain Operations & Inventory Health',
          subtitle: 'Multi-warehouse monitoring across 50 SKUs with real-time stockout risk alerts',
        };
      case 'chat':
        return {
          title: 'GenAI Demand & Inventory Copilot',
          subtitle: 'Multi-model reasoning via OpenRouter with ChromaDB festival & domain RAG retrieval',
        };
      case 'forecast':
        return {
          title: 'Prophet & SARIMA Statistical Forecasting Engine',
          subtitle: 'Daily timeseries decomposition with Indian festival regressor adjustments & confidence bands',
        };
      case 'transfers':
        return {
          title: 'Inter-Warehouse Stock Rebalancing',
          subtitle: 'Optimize surplus-to-deficit transfers vs. external supplier purchase lead times',
        };
      case 'whatif':
        return {
          title: 'What-If Scenario Stress Testing',
          subtitle: 'Simulate demand surges, festive spikes, and supplier delays to evaluate stockout risks',
        };
      case 'approvals':
        return {
          title: 'Human-in-the-Loop Approval Queue',
          subtitle: 'Review, calibrate, and execute AI-generated purchase orders and transfer proposals',
        };
      default:
        return { title: 'GenAI Inventory Assistant' };
    }
  };

  const meta = getPageMeta();

  return (
    <div className="app-container">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={(tab) => handleNavigate(tab)}
        pendingApprovalsCount={pendingApprovalsCount}
        alertCount={alertCount}
      />

      <div className="main-content">
        <Topbar
          title={meta.title}
          subtitle={meta.subtitle}
          isBackendHealthy={isHealthy}
        />

        {activeTab === 'dashboard' && <DashboardView onNavigate={handleNavigate} />}
        {activeTab === 'chat' && (
          <ChatView
            initialSkuId={navContext.skuId}
            initialWarehouseId={navContext.warehouseId}
            onNavigate={handleNavigate}
          />
        )}
        {activeTab === 'forecast' && (
          <ForecastView
            initialSkuId={navContext.skuId}
            initialWarehouseId={navContext.warehouseId}
          />
        )}
        {activeTab === 'transfers' && (
          <TransfersView
            initialSkuId={navContext.skuId}
            initialWarehouseId={navContext.warehouseId}
          />
        )}
        {activeTab === 'whatif' && <WhatIfView />}
        {activeTab === 'approvals' && <ApprovalsView />}
      </div>
    </div>
  );
};

export default App;
