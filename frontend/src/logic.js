export function shuffledOptions(item, random=Math.random) {
  const options=item.options.map((text,originalIndex)=>({text,originalIndex}));
  if(item.stimulus?.type==='circles')return options;
  for(let i=options.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[options[i],options[j]]=[options[j],options[i]];}
  return options;
}
// Grid jitter guarantees separation even for a constant random source.
export function generateDots(count, random=Math.random, width=440, height=240, radius=5) {
  if(!Number.isInteger(count)||count<0||count>100)throw new Error('Dot count must be 0–100');
  const columns=11, rows=10, cellWidth=width/columns, cellHeight=height/rows;
  if(Math.min(cellWidth,cellHeight)<radius*2+2)throw new Error('Box is too small');
  const cells=Array.from({length:columns*rows},(_,i)=>i);
  for(let i=cells.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[cells[i],cells[j]]=[cells[j],cells[i]];}
  return cells.slice(0,count).map(i=>({x:(i%columns+.5)*cellWidth+(random()-.5)*(cellWidth-radius*2-2),y:(Math.floor(i/columns)+.5)*cellHeight+(random()-.5)*(cellHeight-radius*2-2)}));
}
export const remainingSeconds=(deadline,now)=>Math.max(0,Math.ceil((deadline-now)/1000));
export function startTimer({deadline,now=()=>performance.now(),onTick,onExpire,interval=100}) {
  let active=true;
  const tick=()=>{if(!active)return;onTick(remainingSeconds(deadline,now()));if(now()>=deadline){active=false;clearInterval(id);onExpire();}};
  const id=setInterval(tick,interval);tick();
  return ()=>{active=false;clearInterval(id);};
}
