import {useState} from 'react';
import {generateDots} from '../logic';
export default function DotStimulus({count}){const [dots]=useState(()=>generateDots(count));return <svg role="img" aria-label="Brief dot display; estimate the count" viewBox="0 0 440 240" className="mx-auto h-60 w-full max-w-lg rounded-lg border border-line bg-paper">{dots.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r="5" fill="#245de0"/>)}</svg>}
