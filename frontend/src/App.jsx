import React from 'react';
import { NavLink, Route, Routes, Link } from 'react-router-dom';
import SessionSetup from './pages/SessionSetup';
import Trial from './pages/Trial';
import Report from './pages/Report';
import Sessions from './pages/Sessions';
import Dashboard from './pages/Dashboard';
class ErrorBoundary extends React.Component {
  state={error:null};
  static getDerivedStateFromError(error){return {error};}
  render(){return this.state.error?<div className="panel mx-auto mt-10 max-w-xl"><h2>Something interrupted this page</h2><p className="my-4 text-muted">Your submitted trials are saved in the database. Reload to continue.</p><button className="btn" onClick={()=>window.location.reload()}>Reload page</button></div>:this.props.children;}
}
export default function App(){return <ErrorBoundary><header className="border-b border-line bg-white"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-5 px-6 py-5"><Link to="/" className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-xl font-bold text-white" aria-hidden="true">◎</span><span className="text-sm font-semibold leading-5">Metacognitive<br/><span className="font-normal text-muted">Calibration Laboratory</span></span></Link><nav className="flex gap-1" aria-label="Main navigation">{[['/','Session setup'],['/sessions','Sessions'],['/dashboard','Dashboard']].map(([to,label])=><NavLink key={to} to={to} end className={({isActive})=>`rounded-lg px-4 py-2 text-sm font-medium ${isActive?'bg-blue-50 text-brand':'text-muted hover:bg-slate-50'}`}>{label}</NavLink>)}</nav><span className="hidden text-xs text-muted lg:block"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-500"/>Local teaching laboratory</span></div></header><main className="mx-auto max-w-7xl px-6 py-9"><Routes><Route path="/" element={<SessionSetup/>}/><Route path="/session/:id" element={<Trial/>}/><Route path="/report/:id" element={<Report/>}/><Route path="/sessions" element={<Sessions/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="*" element={<div className="panel">Page not found. <Link to="/" className="text-brand">Return to setup</Link></div>}/></Routes></main><footer className="mx-auto flex max-w-7xl justify-between gap-4 px-6 py-8 text-xs text-muted"><span>COGNITIVE PSYCHOLOGY · TEACHING & RESEARCH</span><span>Confidence is a prediction. Calibration is the evidence.</span></footer></ErrorBoundary>}
