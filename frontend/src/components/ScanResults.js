
import React, { useState, useEffect, useRef } from "react";
import { getScans, getScanDetail, triggerScan, markFalsePositive, unmarkFalsePositive, getScanStatus, getPRScans, getPRScanDetail, triggerTrufflehogScan, getTrufflehogScanStatus, getTrufflehogScans, getTrufflehogScanDetail, markTrufflehogFalsePositive, unmarkTrufflehogFalsePositive } from "../api";

// Parse date string from backend (may be missing Z suffix) and format in user's local timezone
function formatDate(dateStr) {
  if (!dateStr) return '';
  // Append 'Z' if no timezone info present so JS treats it as UTC
  const iso = /[Zz]|[+-]\d{2}:?\d{2}$/.test(dateStr) ? dateStr : dateStr + 'Z';
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

// ─── Finding Detail Drawer ────────────────────────────────────────────────────
function FindingDrawer({ finding, onClose, onMarkFP, onUnmarkFP, isAdmin }) {
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    setActiveTab('overview');
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [finding, onClose]);

  if (!finding) return null;

  const meta   = finding.extra?.metadata || {};
  const sev    = finding.extra?.severity  || '';
  const isFP   = finding.status === 'false_positive';

  const sevColor = (s) => {
    const l = (s || '').toLowerCase();
    if (l === 'error')   return { bg: '#fef2f2', color: '#dc2626', border: '#fecaca' };
    if (l === 'warning') return { bg: '#fffbeb', color: '#d97706', border: '#fde68a' };
    return                      { bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe' };
  };
  const sc = sevColor(sev);

  const Tab = ({ id, label }) => (
    <button
      onClick={() => setActiveTab(id)}
      style={{
        padding: '7px 16px', border: 'none', cursor: 'pointer', fontSize: '0.85rem',
        borderBottom: activeTab === id ? '2px solid #2563eb' : '2px solid transparent',
        marginBottom: '-2px', background: 'transparent',
        fontWeight: activeTab === id ? 700 : 400,
        color: activeTab === id ? '#2563eb' : '#64748b',
      }}
    >{label}</button>
  );

  const Row = ({ label, children }) => (
    <div style={{ display: 'flex', gap: '12px', padding: '8px 0', borderBottom: '1px solid #f1f5f9', alignItems: 'flex-start' }}>
      <span style={{ minWidth: '130px', fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', paddingTop: '2px' }}>{label}</span>
      <span style={{ fontSize: '0.875rem', color: '#1e293b', flex: 1, wordBreak: 'break-word' }}>{children || '—'}</span>
    </div>
  );

  const Pill = ({ text, bg = '#f1f5f9', color = '#334155' }) => (
    <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '10px', fontSize: '0.78rem', fontWeight: 600, background: bg, color, marginRight: '6px', marginBottom: '4px' }}>
      {text}
    </span>
  );

  return (
    <>
      {/* backdrop */}
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 900 }} />

      {/* drawer */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(560px, 90vw)',
        background: '#fff', zIndex: 901, display: 'flex', flexDirection: 'column',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        animation: 'slideInRight 0.22s ease',
      }}>

        {/* header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ padding: '3px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700,
                background: sc.bg, color: sc.color, border: `1px solid ${sc.border}` }}>
                {sev}
              </span>
              {isFP && <span style={{ padding: '3px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700, background: '#f1f5f9', color: '#64748b' }}>False Positive</span>}
            </div>
            <div style={{ fontSize: '0.82rem', color: '#64748b', fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {finding.path}:{finding.start?.line}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.4rem', color: '#94a3b8', padding: '0 4px', lineHeight: 1 }}>×</button>
        </div>

        {/* tabs */}
        <div style={{ display: 'flex', borderBottom: '2px solid #e5e7eb', paddingLeft: '12px', flexShrink: 0 }}>
          <Tab id="overview"   label="Overview" />
          <Tab id="details"    label="Details" />
          <Tab id="references" label="References" />
          {finding.extra?.fix && <Tab id="fix" label="Fix" />}
        </div>

        {/* body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>

          {activeTab === 'overview' && (
            <div>
              <div style={{ padding: '14px 16px', background: sc.bg, border: `1px solid ${sc.border}`,
                borderRadius: '8px', marginBottom: '16px', fontSize: '0.875rem', color: '#1e293b', lineHeight: 1.6 }}>
                {finding.extra?.message}
              </div>
              <Row label="Rule ID">
                <span style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{finding.check_id}</span>
              </Row>
              <Row label="File">
                <span style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{finding.path}</span>
              </Row>
              <Row label="Location">Line {finding.start?.line}, Col {finding.start?.col}</Row>
              <Row label="Severity">
                <span style={{ fontWeight: 700, color: sc.color }}>{sev}</span>
              </Row>
              <Row label="Confidence">{meta.confidence}</Row>
              <Row label="Category">{meta.category}</Row>
              {finding.extra?.lines && (
                <div style={{ marginTop: '12px' }}>
                  <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', marginBottom: '6px' }}>Matched Code</div>
                  <pre style={{ background: '#0f172a', color: '#e2e8f0', padding: '12px 16px', borderRadius: '8px',
                    fontSize: '0.82rem', overflowX: 'auto', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {finding.extra.lines}
                  </pre>
                </div>
              )}
            </div>
          )}

          {activeTab === 'details' && (
            <div>
              {(() => {
                // Normalize any field that may be a string or array into always an array
                const toArr = (v) => !v ? [] : Array.isArray(v) ? v : [v];
                const vulClasses = toArr(meta.vulnerability_class);
                const cwes       = toArr(meta.cwe);
                const owasps     = toArr(meta.owasp);
                const techs      = toArr(meta.technology);
                const subcats    = toArr(meta.subcategory);
                return (<>
                  <Row label="Vulnerability Class">
                    <div>{vulClasses.map((c, i) => <Pill key={i} text={c} bg="#ede9fe" color="#5b21b6" />)}</div>
                  </Row>
                  <Row label="CWE">
                    <div>{cwes.map((c, i) => <Pill key={i} text={c} bg="#fef3c7" color="#92400e" />)}</div>
                  </Row>
                  <Row label="OWASP">
                    <div>{owasps.map((o, i) => <Pill key={i} text={o} bg="#ecfdf5" color="#065f46" />)}</div>
                  </Row>
                  <Row label="Technology">
                    <div>{techs.map((t, i) => <Pill key={i} text={t} />)}</div>
                  </Row>
                  <Row label="Subcategory">
                    <div>{subcats.map((s, i) => <Pill key={i} text={s} />)}</div>
                  </Row>
                  <Row label="Likelihood">{meta.likelihood}</Row>
                  <Row label="Impact">{meta.impact}</Row>
                  <Row label="Engine">{finding.extra?.engine_kind}</Row>
                  <Row label="Fingerprint">
                    <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', wordBreak: 'break-all' }}>{finding.extra?.fingerprint}</span>
                  </Row>
                </>);
              })()}
            </div>
          )}

          {activeTab === 'references' && (
            <div>
              {meta.source && (
                <Row label="Rule Source">
                  <a href={meta.source} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>{meta.source}</a>
                </Row>
              )}
              {meta.shortlink && (
                <Row label="Short Link">
                  <a href={meta.shortlink} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb' }}>{meta.shortlink}</a>
                </Row>
              )}
              {(meta.references || []).length > 0 && (
                <Row label="References">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {meta.references.map((r, i) => (
                      <a key={i} href={r} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>{r}</a>
                    ))}
                  </div>
                </Row>
              )}
              {meta.license && (
                <Row label="License">
                  <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>{meta.license}</span>
                </Row>
              )}
            </div>
          )}

          {activeTab === 'fix' && finding.extra?.fix && (
            <div>
              <div style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>Suggested Fix</div>
              <pre style={{ background: '#0f172a', color: '#86efac', padding: '16px', borderRadius: '8px',
                fontSize: '0.85rem', overflowX: 'auto', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all', lineHeight: 1.6 }}>
                {finding.extra.fix}
              </pre>
            </div>
          )}

        </div>

        {/* footer actions */}
        {isAdmin && (
          <div style={{ padding: '12px 20px', borderTop: '1px solid #e5e7eb', display: 'flex', gap: '8px' }}>
            {isFP ? (
              <button className="secondary" style={{ fontSize: '0.85rem', padding: '7px 16px' }}
                onClick={() => { onUnmarkFP(finding.unique_key); onClose(); }}>
                Remove from False Positives
              </button>
            ) : (
              <button className="secondary" style={{ fontSize: '0.85rem', padding: '7px 16px' }}
                onClick={() => { onMarkFP(finding.unique_key); onClose(); }}>
                Mark as False Positive
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
// ─────────────────────────────────────────────────────────────────────────────

// ─── TruffleHog Finding Detail Drawer ─────────────────────────────────────────
function TrufflehogDrawer({ finding, onClose, onMarkFP, onUnmarkFP, isAdmin }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [finding, onClose]);

  if (!finding) return null;

  const git = finding.SourceMetadata?.Data?.Git || {};
  const isFP = finding.status === 'false_positive';
  const verified = finding.Verified;

  const Row = ({ label, children }) => (
    <div style={{ display: 'flex', gap: '12px', padding: '8px 0', borderBottom: '1px solid #f1f5f9', alignItems: 'flex-start' }}>
      <span style={{ minWidth: '130px', fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', paddingTop: '2px' }}>{label}</span>
      <span style={{ fontSize: '0.875rem', color: '#1e293b', flex: 1, wordBreak: 'break-word' }}>{children || '—'}</span>
    </div>
  );

  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 900 }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(560px, 90vw)',
        background: '#fff', zIndex: 901, display: 'flex', flexDirection: 'column',
        boxShadow: '-4px 0 24px rgba(0,0,0,0.12)',
        animation: 'slideInRight 0.22s ease',
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
              <span style={{ padding: '3px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700,
                background: verified ? '#fef2f2' : '#fffbeb', color: verified ? '#dc2626' : '#d97706',
                border: `1px solid ${verified ? '#fecaca' : '#fde68a'}` }}>
                {verified ? 'VERIFIED' : 'UNVERIFIED'}
              </span>
              <span style={{ padding: '3px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700,
                background: '#ede9fe', color: '#5b21b6' }}>
                {finding.DetectorName}
              </span>
              {isFP && <span style={{ padding: '3px 10px', borderRadius: '6px', fontSize: '0.78rem', fontWeight: 700, background: '#f1f5f9', color: '#64748b' }}>False Positive</span>}
            </div>
            <div style={{ fontSize: '0.82rem', color: '#64748b', fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {git.file}:{git.line}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.4rem', color: '#94a3b8', padding: '0 4px', lineHeight: 1 }}>×</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
          {finding.DetectorDescription && (
            <div style={{ padding: '14px 16px', background: '#eff6ff', border: '1px solid #bfdbfe',
              borderRadius: '8px', marginBottom: '16px', fontSize: '0.875rem', color: '#1e293b', lineHeight: 1.6 }}>
              {finding.DetectorDescription}
            </div>
          )}
          <Row label="Detector">{finding.DetectorName} (Type {finding.DetectorType})</Row>
          <Row label="File"><span style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>{git.file}</span></Row>
          <Row label="Line">{git.line}</Row>
          <Row label="Commit"><span style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{git.commit}</span></Row>
          <Row label="Author">{git.email}</Row>
          <Row label="Date">{git.timestamp}</Row>
          <Row label="Decoder">{finding.DecoderName}</Row>
          <Row label="Verified">{verified ? '✅ Yes' : '❌ No'}</Row>
          <Row label="Redacted">{finding.Redacted || '—'}</Row>
          {finding.ExtraData?.rotation_guide && (
            <Row label="Rotation Guide">
              <a href={finding.ExtraData.rotation_guide} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>
                {finding.ExtraData.rotation_guide}
              </a>
            </Row>
          )}
        </div>

        {isAdmin && (
          <div style={{ padding: '12px 20px', borderTop: '1px solid #e5e7eb', display: 'flex', gap: '8px' }}>
            {isFP ? (
              <button className="secondary" style={{ fontSize: '0.85rem', padding: '7px 16px' }}
                onClick={() => { onUnmarkFP(finding.unique_key); onClose(); }}>
                Remove from False Positives
              </button>
            ) : (
              <button className="secondary" style={{ fontSize: '0.85rem', padding: '7px 16px' }}
                onClick={() => { onMarkFP(finding.unique_key); onClose(); }}>
                Mark as False Positive
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
// ─────────────────────────────────────────────────────────────────────────────

export default function ScanResults({ project, user }) {
  const [activeTab, setActiveTab] = useState("full"); // "full" | "pr" | "trufflehog"
  const [scanHistory, setScanHistory] = useState([]);
  const [scanDetail, setScanDetail] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [showFalsePositives, setShowFalsePositives] = useState(false);
  const [showLogs, setShowLogs] = useState(true);
  const [selectedFinding, setSelectedFinding] = useState(null);
  const pollRef = useRef(null);

  // PR scans state
  const [prScans, setPrScans] = useState([]);
  const [prScanDetail, setPrScanDetail] = useState(null);

  // TruffleHog state
  const [thScanHistory, setThScanHistory] = useState([]);
  const [thScanDetail, setThScanDetail] = useState(null);
  const [thScanning, setThScanning] = useState(false);
  const [thShowFalsePositives, setThShowFalsePositives] = useState(false);
  const [selectedThFinding, setSelectedThFinding] = useState(null);
  const thPollRef = useRef(null);

  // Poll server scan status so the banner shows even after re-navigation
  useEffect(() => {
    if (!project) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const { scanning: active } = await getScanStatus(project.id);
        if (cancelled) return;
        setScanning(active);
        if (active) {
          pollRef.current = setTimeout(poll, 5000);
        } else {
          // Scan just finished — refresh history
          getScans(project.id).then(setScanHistory);
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(pollRef.current);
    };
  }, [project]);

  // Poll TruffleHog scan status
  useEffect(() => {
    if (!project) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const { scanning: active } = await getTrufflehogScanStatus(project.id);
        if (cancelled) return;
        setThScanning(active);
        if (active) {
          thPollRef.current = setTimeout(poll, 5000);
        } else {
          getTrufflehogScans(project.id).then(setThScanHistory);
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(thPollRef.current);
    };
  }, [project]);

  const isAdmin = user && user.role === "admin";
  
  // Filter states
  const [filters, setFilters] = useState({
    severity: 'all',
    searchText: '',
    vulnerabilityClass: 'all'
  });
  
  // Sort states
  const [sortBy, setSortBy] = useState('severity-desc'); // severity-desc, severity-asc, path-asc, path-desc, line-asc, line-desc

  useEffect(() => {
    if (project) {
      getScans(project.id).then(setScanHistory);
      getPRScans(project.id).then(setPrScans).catch(() => setPrScans([]));
      getTrufflehogScans(project.id).then(setThScanHistory).catch(() => setThScanHistory([]));
      setScanDetail(null);
      setPrScanDetail(null);
      setThScanDetail(null);
      setLogs([]);
    }
  }, [project]);

  const handleScan = async () => {
    setScanning(true);
    setLogs(l => [
      { type: 'info', msg: 'Scan started...' },
      ...l.slice(0, 4)
    ]);
    try {
      await triggerScan(project.id);
      setScanHistory(await getScans(project.id));
      setLogs(l => [
        { type: 'success', msg: 'Scan completed.' },
        ...l.slice(0, 4)
      ]);
    } catch (err) {
      setLogs(l => [
        { type: 'error', msg: `Scan failed: ${err.message}` },
        ...l.slice(0, 4)
      ]);
    } finally {
      setScanning(false);
      clearTimeout(pollRef.current);
    }
  };

  const handleSelectScan = async (scan) => {
    setScanDetail(null);
    setLogs(l => [
      { type: 'info', msg: `Viewing scan from ${new Date(scan.scan_date).toLocaleString()}` },
      ...l.slice(0, 4)
    ]);
    const detail = await getScanDetail(scan.id);
    setScanDetail(detail);
  };

  const handleSelectPRScan = async (prScan) => {
    setPrScanDetail(null);
    const detail = await getPRScanDetail(prScan.id);
    setPrScanDetail(detail);
  };

  const prStatusBadge = (status) => {
    const map = {
      pending:  { bg: '#fef9c3', color: '#92400e', label: '⏳ Pending' },
      success:  { bg: '#dcfce7', color: '#166534', label: '✅ Passed' },
      failure:  { bg: '#fee2e2', color: '#991b1b', label: '❌ Blocked' },
      error:    { bg: '#f1f5f9', color: '#475569', label: '⚠️ Error' },
    };
    const s = map[status] || map.error;
    return (
      <span style={{ padding: '2px 10px', borderRadius: '12px', fontSize: '0.8rem',
        fontWeight: 600, background: s.bg, color: s.color }}>
        {s.label}
      </span>
    );
  };

  const handleMarkFalsePositive = async (uniqueKey) => {
    await markFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Marked as false positive' },
      ...l.slice(0, 4)
    ]);
    if (scanDetail) {
      const detail = await getScanDetail(scanDetail.id);
      setScanDetail(detail);
    }
  };

  const handleUnmarkFalsePositive = async (uniqueKey) => {
    await unmarkFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Removed from false positives' },
      ...l.slice(0, 4)
    ]);
    if (scanDetail) {
      const detail = await getScanDetail(scanDetail.id);
      setScanDetail(detail);
    }
  };

  const buildGitHubUrl = (path, line) => {
    if (!project.github_url || !path) return null;
    // Remove .git suffix and construct file URL
    const baseUrl = project.github_url.replace(/\.git$/, "");
    const lineFragment = line ? `#L${line}` : "";
    return `${baseUrl}/blob/master/${path}${lineFragment}`;
  };

  const buildSemgrepUrl = (checkId) => {
    if (!checkId) return null;
    return `https://semgrep.dev/r/${checkId}`;
  };

  // TruffleHog handlers
  const handleTrufflehogScan = async () => {
    setThScanning(true);
    setLogs(l => [
      { type: 'info', msg: 'TruffleHog scan started...' },
      ...l.slice(0, 4)
    ]);
    try {
      await triggerTrufflehogScan(project.id);
      setThScanHistory(await getTrufflehogScans(project.id));
      setLogs(l => [
        { type: 'success', msg: 'TruffleHog scan completed.' },
        ...l.slice(0, 4)
      ]);
    } catch (err) {
      setLogs(l => [
        { type: 'error', msg: `TruffleHog scan failed: ${err.message}` },
        ...l.slice(0, 4)
      ]);
    } finally {
      setThScanning(false);
      clearTimeout(thPollRef.current);
    }
  };

  const handleSelectThScan = async (scan) => {
    setThScanDetail(null);
    setLogs(l => [
      { type: 'info', msg: `Viewing TruffleHog scan from ${new Date(scan.scan_date).toLocaleString()}` },
      ...l.slice(0, 4)
    ]);
    const detail = await getTrufflehogScanDetail(scan.id);
    setThScanDetail(detail);
  };

  const handleMarkThFP = async (uniqueKey) => {
    await markTrufflehogFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Marked as false positive' },
      ...l.slice(0, 4)
    ]);
    if (thScanDetail) {
      const detail = await getTrufflehogScanDetail(thScanDetail.id);
      setThScanDetail(detail);
    }
  };

  const handleUnmarkThFP = async (uniqueKey) => {
    await unmarkTrufflehogFalsePositive(project.id, uniqueKey);
    setLogs(l => [
      { type: 'success', msg: 'Removed from false positives' },
      ...l.slice(0, 4)
    ]);
    if (thScanDetail) {
      const detail = await getTrufflehogScanDetail(thScanDetail.id);
      setThScanDetail(detail);
    }
  };

  const badgeColor = (sev) => {
    if (!sev) return '';
    const sevLower = sev.toLowerCase();
    if (sevLower === 'error' || sevLower === 'critical' || sevLower === 'c') return 'badge badge-error';
    if (sevLower === 'warning' || sevLower === 'high' || sevLower === 'h' || sevLower === 'medium' || sevLower === 'm') return 'badge badge-warning';
    if (sevLower === 'info' || sevLower === 'low' || sevLower === 'l') return 'badge badge-info';
    return 'badge';
  };

  return (
    <div className="project-detail">
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ marginBottom: '8px' }}>{(() => {
          // Extract project name as org/repo
          if (project.github_url) {
            const parts = project.github_url.replace(/\.git$/, '').split('/').filter(s => s && !s.includes(':'));
            return parts.slice(-2).join('/') || 'Unnamed';
          } else if (project.local_path) {
            return project.local_path.split('/').filter(part => part).pop();
          } else if (project.name) {
            return project.name;
          }
          return 'Unnamed';
        })()}</h2>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: 500 }}>
            📋 {scanHistory.length} {scanHistory.length === 1 ? 'scan' : 'scans'} in history
          </span>
          {scanHistory.length > 0 && (
            <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              • Last scan: {formatDate(scanHistory[0].scan_date)}
            </span>
          )}
        </div>
      </div>

      {/* Tab switcher */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '20px', borderBottom: '2px solid #e5e7eb', paddingBottom: '0' }}>
        {['full', 'trufflehog', 'pr'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 20px',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid #2563eb' : '2px solid transparent',
              marginBottom: '-2px',
              background: 'transparent',
              fontWeight: activeTab === tab ? 700 : 400,
              color: activeTab === tab ? '#2563eb' : '#64748b',
              cursor: 'pointer',
              fontSize: '0.95rem',
            }}
          >
            {tab === 'full' ? '🔍 SAST Scans' : tab === 'trufflehog' ? `🔑 Secret Scans${thScanHistory.length > 0 ? ` (${thScanHistory.length})` : ''}` : `🔔 PR Scans${prScans.length > 0 ? ` (${prScans.length})` : ''}`}
          </button>
        ))}
      </div>

      {/* ─── FULL SCANS TAB ─── */}
      {activeTab === 'full' && (<>

      <div className="project-controls">
        {scanning && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '10px 16px', marginBottom: '12px',
            background: '#eff6ff', border: '1px solid #bfdbfe',
            borderRadius: '8px', color: '#1e40af', fontSize: '0.9rem', fontWeight: 500
          }}>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            Scan in progress — this may take a few minutes...
          </div>
        )}
        <button 
          onClick={handleScan} 
          disabled={scanning || !isAdmin} 
          className="primary-btn"
          title={!isAdmin ? "Admin access required" : ""}
        >
          {scanning ? "Scanning..." : "Run Security Scan"}
        </button>
        {!isAdmin && (
          <span style={{ fontSize: '0.9rem', color: '#dc2626', marginLeft: '12px' }}>
            🔒 View-only mode (Admin access required for scans)
          </span>
        )}
      </div>

      {logs.length > 0 && (
        <div className="scan-logs-container">
          <div 
            className="scan-logs-header" 
            onClick={() => setShowLogs(!showLogs)}
            style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: showLogs ? '12px' : '0' }}
          >
            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#334155' }}>
              Recent Activity ({logs.length})
            </span>
            <span style={{ fontSize: '1.2rem', color: '#64748b' }}>
              {showLogs ? '▼' : '▶'}
            </span>
          </div>
          {showLogs && (
            <div className="scan-logs-list">
              {logs.slice(0, 3).map((log, i) => (
                <div key={i} className={`log log-${log.type}`}>{log.msg}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="scan-history-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0 }}>Scan History</h3>
        </div>
        {scanHistory.length > 0 ? (
        <div className="scan-history-compact">
          {scanHistory.map((scan, idx) => (
            <button
              key={scan.id}
              className={`scan-history-row${scanDetail && scanDetail.id === scan.id ? ' active' : ''}`}
              onClick={() => handleSelectScan(scan)}
            >
              <span className="scan-history-row-num">#{idx + 1}</span>
              <span className="scan-history-row-date">{formatDate(scan.scan_date)}</span>
              <span className="finding-count">{scan.findings_count} findings</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="empty-message">No scans yet. Click "Run Security Scan" to trigger a scan.</p>
      )}
      </div>

      {scanDetail && (
        <>
          <div className="scan-detail-section">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h4 style={{ margin: 0 }}>Open Findings</h4>
              <button 
                onClick={() => setShowFalsePositives(!showFalsePositives)}
                className="secondary"
                style={{ fontSize: "0.9rem", padding: "8px 16px" }}
              >
                {showFalsePositives ? "Hide" : "Show"} False Positives ({scanDetail.result_json?.false_positives?.length || 0})
              </button>
            </div>
            
            {/* Filter Controls */}
            <div className="filters-container">
              <div className="filter-group">
                <label>Severity:</label>
                <select 
                  value={filters.severity} 
                  onChange={(e) => setFilters({...filters, severity: e.target.value})}
                  className="filter-select"
                >
                  <option value="all">All Severities</option>
                  <option value="error">ERROR</option>
                  <option value="warning">WARNING</option>
                  <option value="info">INFO</option>
                </select>
              </div>
              
              <div className="filter-group">
                <label>Search:</label>
                <input 
                  type="text"
                  placeholder="Filter by path, line, or class..."
                  value={filters.searchText}
                  onChange={(e) => setFilters({...filters, searchText: e.target.value})}
                  className="filter-input"
                />
              </div>
              
              <div className="filter-group">
                <label>Sort By:</label>
                <select 
                  value={sortBy} 
                  onChange={(e) => setSortBy(e.target.value)}
                  className="filter-select"
                >
                  <option value="severity-desc">Severity (High → Low)</option>
                  <option value="severity-asc">Severity (Low → High)</option>
                  <option value="path-asc">Path (A → Z)</option>
                  <option value="path-desc">Path (Z → A)</option>
                  <option value="line-asc">Line (Low → High)</option>
                  <option value="line-desc">Line (High → Low)</option>
                </select>
              </div>
              
              {filters.severity !== 'all' || filters.searchText ? (
                <button 
                  onClick={() => setFilters({ severity: 'all', searchText: '', vulnerabilityClass: 'all' })}
                  className="clear-filters-btn"
                >
                  Clear Filters
                </button>
              ) : null}
            </div>
            
            {Array.isArray(scanDetail.result_json?.results) && scanDetail.result_json.results.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Line</th>
                    <th>Class</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {scanDetail.result_json.results
                    .filter(vul => {
                      // Filter by severity
                      if (filters.severity !== 'all') {
                        const vulSeverity = (vul.extra?.severity || '').toLowerCase();
                        const filterSev = filters.severity.toLowerCase();
                        
                        // Map old severity values to new ones for compatibility
                        let normalizedVulSev = vulSeverity;
                        if (vulSeverity === 'critical' || vulSeverity === 'c') normalizedVulSev = 'error';
                        if (vulSeverity === 'high' || vulSeverity === 'h' || vulSeverity === 'medium' || vulSeverity === 'm') normalizedVulSev = 'warning';
                        if (vulSeverity === 'low' || vulSeverity === 'l') normalizedVulSev = 'info';
                        
                        if (normalizedVulSev !== filterSev && vulSeverity !== filterSev) {
                          return false;
                        }
                      }
                      
                      // Filter by search text
                      if (filters.searchText) {
                        const searchLower = filters.searchText.toLowerCase();
                        const path = (vul.path || '').toLowerCase();
                        const line = (vul.start?.line || '').toString();
                        const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                          ? vul.extra.metadata.vulnerability_class.join(', ').toLowerCase()
                          : (vul.extra?.metadata?.vulnerability_class || '').toLowerCase();
                        const checkId = (vul.check_id || '').toLowerCase();
                        
                        if (!path.includes(searchLower) && 
                            !line.includes(searchLower) && 
                            !vulClass.includes(searchLower) &&
                            !checkId.includes(searchLower)) {
                          return false;
                        }
                      }
                      
                      return true;
                    })
                    .sort((a, b) => {
                      // Sort logic
                      const [field, direction] = sortBy.split('-');
                      let comparison = 0;
                      
                      if (field === 'severity') {
                        // Define severity order (ERROR > WARNING > INFO)
                        const severityOrder = { error: 3, warning: 2, info: 1 };
                        const getSeverityValue = (vul) => {
                          const sev = (vul.extra?.severity || '').toLowerCase();
                          // Map old values to new
                          if (sev === 'critical' || sev === 'c') return severityOrder.error;
                          if (sev === 'high' || sev === 'h' || sev === 'medium' || sev === 'm') return severityOrder.warning;
                          if (sev === 'low' || sev === 'l' || sev === 'info') return severityOrder.info;
                          if (sev === 'error') return severityOrder.error;
                          if (sev === 'warning') return severityOrder.warning;
                          return 0;
                        };
                        comparison = getSeverityValue(b) - getSeverityValue(a);
                        if (direction === 'asc') comparison = -comparison;
                      } else if (field === 'path') {
                        const pathA = (a.path || '').toLowerCase();
                        const pathB = (b.path || '').toLowerCase();
                        comparison = pathA.localeCompare(pathB);
                        if (direction === 'desc') comparison = -comparison;
                      } else if (field === 'line') {
                        const lineA = a.start?.line || 0;
                        const lineB = b.start?.line || 0;
                        comparison = lineA - lineB;
                        if (direction === 'desc') comparison = -comparison;
                      }
                      
                      return comparison;
                    })
                    .map((vul, idx) => {
                    const githubUrl = buildGitHubUrl(vul.path, vul.start?.line);
                    const semgrepUrl = buildSemgrepUrl(vul.check_id);
                    const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                      ? vul.extra.metadata.vulnerability_class.join(", ") 
                      : vul.extra?.metadata?.vulnerability_class || '';
                    
                    return (
                      <tr key={idx} onClick={() => setSelectedFinding(vul)} style={{ cursor: 'pointer' }} title="Click to view details">
                        <td>
                          {githubUrl ? (
                            <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>
                              {vul.path}
                            </a>
                          ) : (
                            vul.path
                          )}
                        </td>
                        <td>{vul.start?.line}</td>
                        <td>
                          {semgrepUrl && vulClass ? (
                            <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>
                              {vulClass}
                            </a>
                          ) : (
                            vulClass
                          )}
                        </td>
                        <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        <td><span className="badge" style={{ background: "#10b981" }}>{vul.status || "open"}</span></td>
                        <td>
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleMarkFalsePositive(vul.unique_key); }}
                            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            className="secondary"
                            disabled={!isAdmin}
                            title={!isAdmin ? "Admin access required" : ""}
                          >
                            Mark as FP
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <span className="empty-message">No open vulnerabilities found.</span>
            )}
          </div>

          {showFalsePositives && scanDetail.result_json?.false_positives && scanDetail.result_json.false_positives.length > 0 && (
            <div className="scan-detail-section" style={{ marginTop: "32px" }}>
              <h4>False Positives</h4>
              <table>
                <thead>
                  <tr>
                    <th>Path</th>
                    <th>Line</th>
                    <th>Class</th>
                    <th>Severity</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {scanDetail.result_json.false_positives.map((vul, idx) => {
                    const semgrepUrl = buildSemgrepUrl(vul.check_id);
                    const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class) 
                      ? vul.extra.metadata.vulnerability_class.join(", ") 
                      : vul.extra?.metadata?.vulnerability_class || '';
                    
                    return (
                      <tr key={idx} style={{ background: "#fef2f2", cursor: 'pointer' }} onClick={() => setSelectedFinding(vul)} title="Click to view details">
                        <td>{vul.path}</td>
                        <td>{vul.start?.line}</td>
                        <td>
                          {semgrepUrl && vulClass ? (
                            <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>
                              {vulClass}
                            </a>
                          ) : (
                            vulClass
                          )}
                        </td>
                        <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        <td><span className="badge" style={{ background: "#64748b" }}>False Positive</span></td>
                        <td>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleUnmarkFalsePositive(vul.unique_key); }}
                            style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                            className="secondary"
                            disabled={!isAdmin}
                            title={!isAdmin ? "Admin access required" : "Remove from false positives"}
                          >
                            Remove FP
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
        </>
      )}

      {/* ─── TRUFFLEHOG SCANS TAB ─── */}
      {activeTab === 'trufflehog' && (<>
        <div className="project-controls">
          {thScanning && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '10px',
              padding: '10px 16px', marginBottom: '12px',
              background: '#fef3c7', border: '1px solid #fde68a',
              borderRadius: '8px', color: '#92400e', fontSize: '0.9rem', fontWeight: 500
            }}>
              <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
              TruffleHog scan in progress — this may take a few minutes...
            </div>
          )}
          <button
            onClick={handleTrufflehogScan}
            disabled={thScanning || !isAdmin}
            className="primary-btn"
            style={{ background: '#7c3aed' }}
            title={!isAdmin ? "Admin access required" : ""}
          >
            {thScanning ? "Scanning..." : "Run Secret Scan"}
          </button>
          {!isAdmin && (
            <span style={{ fontSize: '0.9rem', color: '#dc2626', marginLeft: '12px' }}>
              🔒 View-only mode (Admin access required for scans)
            </span>
          )}
        </div>

        <div className="scan-history-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ margin: 0 }}>TruffleHog Scan History</h3>
          </div>
          {thScanHistory.length > 0 ? (
            <div className="scan-history-compact">
              {thScanHistory.map((scan, idx) => (
                <button
                  key={scan.id}
                  className={`scan-history-row${thScanDetail && thScanDetail.id === scan.id ? ' active' : ''}`}
                  onClick={() => handleSelectThScan(scan)}
                >
                  <span className="scan-history-row-num">#{idx + 1}</span>
                  <span className="scan-history-row-date">{formatDate(scan.scan_date)}</span>
                  <span className="finding-count">{scan.findings_count} secrets</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="empty-message">No TruffleHog scans yet. Click "Run Secret Scan" to trigger a scan.</p>
          )}
        </div>

        {thScanDetail && (
          <>
            <div className="scan-detail-section">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                <h4 style={{ margin: 0 }}>Open Secrets</h4>
                <button
                  onClick={() => setThShowFalsePositives(!thShowFalsePositives)}
                  className="secondary"
                  style={{ fontSize: "0.9rem", padding: "8px 16px" }}
                >
                  {thShowFalsePositives ? "Hide" : "Show"} False Positives ({thScanDetail.result_json?.false_positives?.length || 0})
                </button>
              </div>

              {/* TH Filter Controls */}
              <div className="filters-container">
                <div className="filter-group">
                  <label>Search:</label>
                  <input
                    type="text"
                    placeholder="Filter by file, detector, or commit..."
                    value={filters.searchText}
                    onChange={(e) => setFilters({...filters, searchText: e.target.value})}
                    className="filter-input"
                  />
                </div>
                {filters.searchText ? (
                  <button
                    onClick={() => setFilters({ severity: 'all', searchText: '', vulnerabilityClass: 'all' })}
                    className="clear-filters-btn"
                  >
                    Clear Filters
                  </button>
                ) : null}
              </div>

              {Array.isArray(thScanDetail.result_json?.results) && thScanDetail.result_json.results.length > 0 ? (
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Line</th>
                      <th>Detector</th>
                      <th>Verified</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {thScanDetail.result_json.results
                      .filter(f => {
                        if (filters.searchText) {
                          const s = filters.searchText.toLowerCase();
                          const file = (f.SourceMetadata?.Data?.Git?.file || '').toLowerCase();
                          const detector = (f.DetectorName || '').toLowerCase();
                          const commit = (f.SourceMetadata?.Data?.Git?.commit || '').toLowerCase();
                          if (!file.includes(s) && !detector.includes(s) && !commit.includes(s)) return false;
                        }
                        return true;
                      })
                      .map((f, idx) => {
                        const git = f.SourceMetadata?.Data?.Git || {};
                        const githubUrl = buildGitHubUrl(git.file, git.line);
                        return (
                          <tr key={idx} onClick={() => setSelectedThFinding(f)} style={{ cursor: 'pointer' }} title="Click to view details">
                            <td>
                              {githubUrl ? (
                                <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>
                                  {git.file}
                                </a>
                              ) : git.file}
                            </td>
                            <td>{git.line}</td>
                            <td><span className="badge" style={{ background: '#ede9fe', color: '#5b21b6' }}>{f.DetectorName}</span></td>
                            <td>
                              <span className={f.Verified ? 'badge badge-error' : 'badge badge-warning'}>
                                {f.Verified ? 'Verified' : 'Unverified'}
                              </span>
                            </td>
                            <td><span className="badge" style={{ background: "#10b981" }}>{f.status || "open"}</span></td>
                            <td>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleMarkThFP(f.unique_key); }}
                                style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                                className="secondary"
                                disabled={!isAdmin}
                                title={!isAdmin ? "Admin access required" : ""}
                              >
                                Mark as FP
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              ) : (
                <span className="empty-message">No open secrets found.</span>
              )}
            </div>

            {thShowFalsePositives && thScanDetail.result_json?.false_positives && thScanDetail.result_json.false_positives.length > 0 && (
              <div className="scan-detail-section" style={{ marginTop: "32px" }}>
                <h4>False Positives</h4>
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Line</th>
                      <th>Detector</th>
                      <th>Verified</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {thScanDetail.result_json.false_positives.map((f, idx) => {
                      const git = f.SourceMetadata?.Data?.Git || {};
                      return (
                        <tr key={idx} style={{ background: "#fef2f2", cursor: 'pointer' }} onClick={() => setSelectedThFinding(f)} title="Click to view details">
                          <td>{git.file}</td>
                          <td>{git.line}</td>
                          <td><span className="badge" style={{ background: '#ede9fe', color: '#5b21b6' }}>{f.DetectorName}</span></td>
                          <td>
                            <span className={f.Verified ? 'badge badge-error' : 'badge badge-warning'}>
                              {f.Verified ? 'Verified' : 'Unverified'}
                            </span>
                          </td>
                          <td><span className="badge" style={{ background: "#64748b" }}>False Positive</span></td>
                          <td>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleUnmarkThFP(f.unique_key); }}
                              style={{ padding: "6px 12px", fontSize: "0.85rem" }}
                              className="secondary"
                              disabled={!isAdmin}
                              title={!isAdmin ? "Admin access required" : "Remove from false positives"}
                            >
                              Remove FP
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* TH Summary */}
            {thScanDetail.result_json?.summary && (
              <div style={{ marginTop: '24px', padding: '16px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <h4 style={{ margin: '0 0 12px 0', fontSize: '0.95rem' }}>Scan Summary</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px' }}>
                  {thScanDetail.result_json.summary.verified_secrets !== undefined && (
                    <div><span style={{ fontWeight: 600, color: '#dc2626' }}>{thScanDetail.result_json.summary.verified_secrets}</span> <span style={{ color: '#64748b', fontSize: '0.85rem' }}>verified</span></div>
                  )}
                  {thScanDetail.result_json.summary.unverified_secrets !== undefined && (
                    <div><span style={{ fontWeight: 600, color: '#d97706' }}>{thScanDetail.result_json.summary.unverified_secrets}</span> <span style={{ color: '#64748b', fontSize: '0.85rem' }}>unverified</span></div>
                  )}
                  {thScanDetail.result_json.summary.scan_duration && (
                    <div><span style={{ fontWeight: 600 }}>{thScanDetail.result_json.summary.scan_duration}</span> <span style={{ color: '#64748b', fontSize: '0.85rem' }}>duration</span></div>
                  )}
                  {thScanDetail.result_json.summary.chunks !== undefined && (
                    <div><span style={{ fontWeight: 600 }}>{thScanDetail.result_json.summary.chunks}</span> <span style={{ color: '#64748b', fontSize: '0.85rem' }}>chunks scanned</span></div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </>)}

      {/* ─── PR SCANS TAB ─── */}
      {activeTab === 'pr' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>PR Scan History</h3>
            <button
              className="secondary"
              style={{ fontSize: '0.85rem', padding: '6px 14px' }}
              onClick={() => getPRScans(project.id).then(setPrScans).catch(() => {})}
            >
              ↻ Refresh
            </button>
          </div>

          {prScans.length === 0 ? (
            <p className="empty-message">
              No PR scans yet. Enable PR Checks in Configurations, add the webhook to your GitHub repo, then open a PR.
            </p>
          ) : (
            <div className="scan-history-compact" style={{ maxHeight: '320px', overflowY: 'auto' }}>
              {prScans.map(pr => (
                <button
                  key={pr.id}
                  className={`scan-history-row${prScanDetail && prScanDetail.id === pr.id ? ' active' : ''}`}
                  onClick={() => handleSelectPRScan(pr)}
                  style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '4px', height: 'auto', padding: '10px 14px' }}
                >
                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center', width: '100%' }}>
                    <span style={{ fontWeight: 700, color: '#2563eb' }}>#{pr.pr_number}</span>
                    <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {pr.pr_title || '(no title)'}
                    </span>
                    {prStatusBadge(pr.status)}
                  </div>
                  <div style={{ display: 'flex', gap: '12px', fontSize: '0.8rem', color: '#64748b' }}>
                    <span>🌿 {pr.head_branch} → {pr.base_branch}</span>
                    <span>📂 {(pr.changed_files || []).length} files</span>
                    <span>🔍 {pr.findings_count} finding{pr.findings_count !== 1 ? 's' : ''}</span>
                    <span>{formatDate(pr.created_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {prScanDetail && (
            <div className="scan-detail-section" style={{ marginTop: '24px' }}>
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 4px 0' }}>
                  PR #{prScanDetail.pr_number}: {prScanDetail.pr_title}
                </h4>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.85rem', color: '#64748b', flexWrap: 'wrap' }}>
                  <span>🌿 {prScanDetail.head_branch} → {prScanDetail.base_branch}</span>
                  <span>🔗 {prScanDetail.head_sha?.slice(0, 8)}</span>
                  <span>Status: {prStatusBadge(prScanDetail.status)}</span>
                </div>
                <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#64748b' }}>
                  <strong>Changed files scanned:</strong>{' '}
                  {(prScanDetail.changed_files || []).join(', ') || 'none'}
                </div>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '6px' }}>
                  ℹ️ Only findings on lines changed in this PR are shown.
                </p>
              </div>

              {prScanDetail.result_json?.error ? (
                <div style={{ padding: '12px', background: '#fef2f2', borderRadius: '8px', color: '#dc2626' }}>
                  Scan error: {prScanDetail.result_json.error}
                </div>
              ) : (prScanDetail.result_json?.results || []).length === 0 ? (
                <p className="empty-message">✅ No SAST issues found in the changed lines.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Path</th>
                      <th>Line</th>
                      <th>Class</th>
                      <th>Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(prScanDetail.result_json.results || []).map((vul, idx) => {
                      const semgrepUrl = buildSemgrepUrl(vul.check_id);
                      const vulClass = Array.isArray(vul.extra?.metadata?.vulnerability_class)
                        ? vul.extra.metadata.vulnerability_class.join(', ')
                        : vul.extra?.metadata?.vulnerability_class || '';
                      const githubUrl = buildGitHubUrl(vul.path, vul.start?.line);
                      return (
                        <tr key={idx} onClick={() => setSelectedFinding(vul)} style={{ cursor: 'pointer' }} title="Click to view details">
                          <td>
                            {githubUrl
                              ? <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>{vul.path}</a>
                              : vul.path}
                          </td>
                          <td>{vul.start?.line}</td>
                          <td>
                            {semgrepUrl && vulClass
                              ? <a href={semgrepUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>{vulClass}</a>
                              : vulClass}
                          </td>
                          <td><span className={badgeColor(vul.extra?.severity)}>{vul.extra?.severity}</span></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}

              {/* TruffleHog secrets found in PR changed lines */}
              <div style={{ marginTop: '28px' }}>
                <h5 style={{ margin: '0 0 10px 0', fontSize: '0.95rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  🔑 Secrets Found in Changed Lines
                  <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '0.78rem',
                    background: (prScanDetail.result_json?.trufflehog_results || []).length > 0 ? '#fef3c7' : '#f1f5f9',
                    color: (prScanDetail.result_json?.trufflehog_results || []).length > 0 ? '#92400e' : '#64748b',
                    fontWeight: 600 }}>
                    {(prScanDetail.result_json?.trufflehog_results || []).length}
                  </span>
                </h5>
                {(prScanDetail.result_json?.trufflehog_results || []).length === 0 ? (
                  <p className="empty-message" style={{ marginTop: 0 }}>✅ No secrets found in the changed lines.</p>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th>File</th>
                        <th>Line</th>
                        <th>Detector</th>
                        <th>Verified</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(prScanDetail.result_json.trufflehog_results || []).map((f, idx) => {
                        const relPath = f._pr_file || f.SourceMetadata?.Data?.Filesystem?.file || '';
                        const line = f.SourceMetadata?.Data?.Filesystem?.line;
                        const githubUrl = buildGitHubUrl(relPath, line);
                        return (
                          <tr key={idx} onClick={() => setSelectedThFinding(f)} style={{ cursor: 'pointer' }} title="Click to view details">
                            <td>
                              {githubUrl
                                ? <a href={githubUrl} target="_blank" rel="noopener noreferrer" className="github-link" onClick={e => e.stopPropagation()}>{relPath}</a>
                                : relPath}
                            </td>
                            <td>{line}</td>
                            <td><span className="badge" style={{ background: '#ede9fe', color: '#5b21b6' }}>{f.DetectorName}</span></td>
                            <td>
                              <span className={f.Verified ? 'badge badge-error' : 'badge badge-warning'}>
                                {f.Verified ? 'Verified' : 'Unverified'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <FindingDrawer
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
        onMarkFP={handleMarkFalsePositive}
        onUnmarkFP={handleUnmarkFalsePositive}
        isAdmin={isAdmin}
      />

      <TrufflehogDrawer
        finding={selectedThFinding}
        onClose={() => setSelectedThFinding(null)}
        onMarkFP={handleMarkThFP}
        onUnmarkFP={handleUnmarkThFP}
        isAdmin={isAdmin}
      />

    </div>
  );
}

