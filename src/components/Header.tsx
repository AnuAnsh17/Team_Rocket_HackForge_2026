import React, { useState } from 'react';
import {
  Search,
  Calendar,
  ShieldCheck,
  User,
  ChevronDown,
  X,
  ExternalLink,
} from 'lucide-react';
import { Claim, ActiveTab } from '../types';

interface HeaderProps {
  activeTab: ActiveTab;
  onNavigate: (tab: ActiveTab) => void;
  onSelectClaim: (claimId: string) => void;
  claims: Claim[];
  currentUserRole: string;
  onOpenLogin: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onNavigate,
  onSelectClaim,
  claims,
  currentUserRole,
  onOpenLogin,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [dateRange, setDateRange] = useState('Oct 1 - Oct 31, 2026');
  const [isDateMenuOpen, setIsDateMenuOpen] = useState(false);

  const filteredSearchResults = searchQuery.trim()
    ? claims.filter(
        (c) =>
          c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
          c.employeeName.toLowerCase().includes(searchQuery.toLowerCase()) ||
          c.employeeId.toLowerCase().includes(searchQuery.toLowerCase()) ||
          c.merchantName.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 5)
    : [];

  const handleSearchResultClick = (claimId: string) => {
    onSelectClaim(claimId);
    onNavigate('workbench');
    setSearchQuery('');
    setShowSearchResults(false);
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-6 backdrop-blur-sm">
      {/* Zone 1: Brand & Active Policy Contract */}
      <div className="flex items-center gap-3">
        <div
          onClick={() => onNavigate('overview')}
          className="flex cursor-pointer items-center gap-2"
        >
          <div className="flex h-7 w-7 items-center justify-center rounded bg-slate-900 text-white font-semibold text-xs tracking-wider">
            PL
          </div>
          <span className="font-bold text-slate-900 tracking-tight text-base whitespace-nowrap">
            Proofline
          </span>
        </div>
        <span className="text-slate-300">/</span>
        <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          <span className="font-mono font-medium text-slate-700">v2026.4</span>
          <span className="text-slate-400">·</span>
          <span className="text-emerald-700 font-medium">Active Policy</span>
        </div>

        <button
          onClick={() => onNavigate(activeTab === 'landing' ? 'overview' : 'landing')}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded transition-colors whitespace-nowrap ${
            activeTab === 'landing'
              ? 'bg-slate-900 text-white font-semibold'
              : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200'
          }`}
          title="Toggle Three.js 3D Landing Page"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
          <span>{activeTab === 'landing' ? 'Console App' : '3D Visuals'}</span>
        </button>
      </div>

      {/* Zone 2: Global Search & Date Range */}
      <div className="flex items-center gap-4 flex-1 max-w-xl mx-8">
        <div className="relative flex-1">
          <div className="relative flex items-center">
            <Search className="absolute left-3 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowSearchResults(true);
              }}
              onFocus={() => setShowSearchResults(true)}
              placeholder="Search Claim ID (e.g. CLM-8491), Employee, or Merchant..."
              className="w-full h-8 pl-8.5 pr-8 text-xs bg-slate-50 border border-slate-200 rounded text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-slate-400 focus:bg-white transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setShowSearchResults(false);
                }}
                className="absolute right-2.5 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Search Dropdown */}
          {showSearchResults && searchQuery.trim() && (
            <div className="absolute top-9 left-0 right-0 bg-white border border-slate-200 rounded-md shadow-lg py-1 z-50">
              <div className="px-3 py-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Matching Expense Claims ({filteredSearchResults.length})
              </div>
              {filteredSearchResults.length > 0 ? (
                filteredSearchResults.map((claim) => (
                  <button
                    key={claim.id}
                    onClick={() => handleSearchResultClick(claim.id)}
                    className="w-full px-3 py-2 text-left hover:bg-slate-50 flex items-center justify-between transition-colors border-t border-slate-100 first:border-none"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-900">
                          {claim.id}
                        </span>
                        <span className="text-xs text-slate-700">
                          {claim.employeeName}
                        </span>
                        <span className="text-[11px] text-slate-400">
                          ({claim.employeeId})
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 truncate max-w-sm">
                        {claim.merchantName} · {claim.category}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-xs font-semibold text-slate-900">
                        ₹{claim.claimedAmount.toLocaleString('en-IN')}
                      </div>
                      <span
                        className={`inline-block text-[10px] font-medium px-1.5 py-0.2 rounded mt-0.5 ${
                          claim.status === 'PASS'
                            ? 'text-emerald-700 bg-emerald-50'
                            : claim.status === 'FAIL'
                            ? 'text-rose-700 bg-rose-50'
                            : 'text-amber-700 bg-amber-50'
                        }`}
                      >
                        {claim.status}
                      </span>
                    </div>
                  </button>
                ))
              ) : (
                <div className="px-3 py-4 text-center text-xs text-slate-500">
                  No matching claims found for "{searchQuery}".
                </div>
              )}
            </div>
          )}
        </div>

        {/* Date Range Selector */}
        <div className="relative">
          <button
            onClick={() => setIsDateMenuOpen(!isDateMenuOpen)}
            className="flex items-center gap-2 h-8 px-2.5 text-xs bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded text-slate-700 transition-colors whitespace-nowrap"
          >
            <Calendar className="h-3.5 w-3.5 text-slate-400" />
            <span className="font-mono text-[11px]">{dateRange}</span>
            <ChevronDown className="h-3 w-3 text-slate-400" />
          </button>
          {isDateMenuOpen && (
            <div className="absolute right-0 top-9 w-44 bg-white border border-slate-200 rounded shadow-md py-1 z-50">
              {['Oct 1 - Oct 31, 2026', 'Sep 1 - Sep 30, 2026', 'Q3 FY27 (Jul - Sep)', 'FY27 Year to Date'].map(
                (range) => (
                  <button
                    key={range}
                    onClick={() => {
                      setDateRange(range);
                      setIsDateMenuOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-50 transition-colors ${
                      dateRange === range ? 'font-semibold text-slate-900 bg-slate-50' : 'text-slate-600'
                    }`}
                  >
                    {range}
                  </button>
                )
              )}
            </div>
          )}
        </div>
      </div>

      {/* Zone 3: User Profile & Auth Switcher */}
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={onOpenLogin}
          className="flex items-center gap-2 px-2.5 py-1 rounded hover:bg-slate-100 text-left transition-colors border border-transparent hover:border-slate-200"
        >
          <div className="h-6 w-6 rounded-full bg-slate-800 text-white flex items-center justify-center text-[11px] font-semibold">
            PS
          </div>
          <div className="text-left hidden sm:block">
            <div className="text-xs font-semibold text-slate-900 leading-tight">
              Preeti S.
            </div>
            <div className="text-[10px] text-slate-500 leading-tight">
              {currentUserRole}
            </div>
          </div>
        </button>

        <button
          onClick={onOpenLogin}
          className="px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors whitespace-nowrap"
        >
          Switch Role / SSO
        </button>
      </div>
    </header>
  );
};
