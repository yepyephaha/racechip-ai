import {useRef, useState} from 'react';
import {createWorker} from 'tesseract.js';
import {FileImage, FileVideo, LoaderCircle, ScanText, Upload} from 'lucide-react';

type Props={onUseAsStatement:(text:string)=>void;onUseAsContext:(text:string)=>void};
type Progress={text:string;percent:number|null};
const MAX_BYTES=100*1024*1024;
const MAX_VIDEO_SECONDS=300;
const MAX_VIDEO_FRAMES=5;

function seek(video:HTMLVideoElement,time:number){
  return new Promise<void>((resolve,reject)=>{
    const timeout=setTimeout(()=>reject(new Error('读取视频帧超时。')),12000);
    const done=()=>{clearTimeout(timeout);video.removeEventListener('seeked',done);video.removeEventListener('error',fail);resolve();};
    const fail=()=>{clearTimeout(timeout);video.removeEventListener('seeked',done);video.removeEventListener('error',fail);reject(new Error('无法解码此视频帧。'));};
    video.addEventListener('seeked',done,{once:true});video.addEventListener('error',fail,{once:true});video.currentTime=time;
  });
}

async function videoFrames(file:File,onProgress:(value:Progress)=>void){
  const video=document.createElement('video');const objectUrl=URL.createObjectURL(file);video.preload='metadata';video.muted=true;video.playsInline=true;
  try{
    await new Promise<void>((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error('读取视频信息超时。')),12000);video.onloadedmetadata=()=>{clearTimeout(timeout);resolve();};video.onerror=()=>{clearTimeout(timeout);reject(new Error('浏览器无法读取该视频，请换用MP4或WebM。'));};video.src=objectUrl;video.load();});
    if(!Number.isFinite(video.duration)||video.duration<=0)throw new Error('没有读取到有效的视频时长。');
    if(video.duration>MAX_VIDEO_SECONDS)throw new Error('视频超过5分钟。请先截取包含相关内容的片段。');
    const width=video.videoWidth,height=video.videoHeight;if(!width||!height)throw new Error('视频没有可识别的画面。');
    const count=Math.min(MAX_VIDEO_FRAMES,Math.max(1,Math.ceil(video.duration/12)));
    const times=Array.from({length:count},(_,index)=>count===1?video.duration/2:Math.max(0,Math.min(video.duration-.05,video.duration*(.08+.84*index/(count-1)))));
    const canvas=document.createElement('canvas');const scale=Math.min(1,1600/Math.max(width,height));canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);
    const context=canvas.getContext('2d');if(!context)throw new Error('无法创建本机视频帧画布。');
    const frames:Blob[]=[];
    for(let index=0;index<times.length;index++){
      onProgress({text:`读取第 ${index+1}/${times.length} 帧`,percent:Math.round(index/times.length*100)});
      await seek(video,times[index]);context.drawImage(video,0,0,canvas.width,canvas.height);
      const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/png'));
      if(blob)frames.push(blob);
    }
    return {frames,times};
  }finally{video.pause();video.removeAttribute('src');video.load();URL.revokeObjectURL(objectUrl);}
}

export default function EvidenceCapture({onUseAsStatement,onUseAsContext}:Props){
  const input=useRef<HTMLInputElement>(null);
  const [progress,setProgress]=useState<Progress|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [text,setText]=useState('');
  const [filename,setFilename]=useState('');
  async function recognize(file?:File){
    if(!file)return;
    setError('');setText('');setFilename(file.name);
    if(file.size>MAX_BYTES){setError('文件超过100MB，请先压缩或截取相关部分。');return;}
    const isImage=['image/png','image/jpeg','image/webp'].includes(file.type);
    const isVideo=['video/mp4','video/webm'].includes(file.type);
    if(!isImage&&!isVideo){setError('目前支持 PNG、JPG、WebP 图片，以及 MP4、WebM 视频。');return;}
    setBusy(true);setProgress({text:'加载中英文识别模型',percent:null});
    let worker:Awaited<ReturnType<typeof createWorker>>|undefined;
    try{
      const frames=isImage?{frames:[file],times:[null as number|null]}:await videoFrames(file,value=>setProgress(value));
      worker=await createWorker(['eng','chi_sim'],1,{logger:message=>{
        if(message.status==='recognizing text')setProgress({text:'正在识别画面文字',percent:Math.round(message.progress*100)});
      }});
      const results:string[]=[];
      for(let index=0;index<frames.frames.length;index++){
        if(isVideo)setProgress({text:`识别视频画面 ${index+1}/${frames.frames.length}`,percent:Math.round(index/frames.frames.length*100)});
        const result=await worker.recognize(frames.frames[index]);
        const value=result.data.text.trim();
        if(value)results.push(isVideo?`[约 ${frames.times[index]?.toFixed(1)} 秒]\n${value}`:value);
      }
      const output=results.join('\n\n');
      if(!output)setError('没有识别到清晰文字。可换一张更清晰的截图，或直接在核验框里描述说法。');
      setText(output);
      setProgress({text:output?'本机识别完成，可编辑后再使用':'识别结束',percent:100});
    }catch(cause){setError(cause instanceof Error?cause.message:'识别失败，请换一种格式重试。');}
    finally{await worker?.terminate();setBusy(false);if(input.current)input.current.value='';}
  }
  return <section className="ev-capture" aria-labelledby="ev-capture-title">
    <div className="ev-capture-heading"><span className="ev-capture-icon"><ScanText size={18}/></span><div><h2 id="ev-capture-title">从截图或视频里提取线索</h2><p>先在本机识别画面文字，再由你选择要核查的内容。</p></div></div>
    <input ref={input} className="ev-capture-file" type="file" accept="image/png,image/jpeg,image/webp,video/mp4,video/webm" onChange={event=>void recognize(event.target.files?.[0])} disabled={busy}/>
    <button type="button" className="ev-capture-select" onClick={()=>input.current?.click()} disabled={busy}>
      {busy?<LoaderCircle size={17} className="ev-spin"/>:filename.toLowerCase().endsWith('.mp4')||filename.toLowerCase().endsWith('.webm')?<FileVideo size={17}/>:<FileImage size={17}/>}
      <span>{busy?'正在识别…':filename||'选择图片或视频'}</span><Upload size={15}/>
    </button>
    {progress&&<div className="ev-capture-progress" role="status" aria-live="polite"><span>{progress.text}</span>{progress.percent!==null&&<span>{progress.percent}%</span>}</div>}
    {busy&&<div className="ev-progress-track" aria-hidden="true"><i style={{width:`${progress?.percent??12}%`}}/></div>}
    {text&&<><label className="ev-capture-label" htmlFor="ev-capture-text">识别结果 · 可编辑</label><textarea id="ev-capture-text" rows={5} value={text} onChange={event=>setText(event.target.value)} maxLength={8000}/><div className="ev-capture-actions"><button type="button" className="hw-button" onClick={()=>onUseAsStatement(text.slice(0,4000))}>作为待核查说法</button><button type="button" className="hw-button" onClick={()=>onUseAsContext(text.slice(0,2000))}>补充为核查背景</button></div></>}
    {error&&<p className="ev-capture-error" role="alert">{error}</p>}
    <p className="ev-capture-privacy">仅抽取最多5帧、5分钟内的视频片段；原始媒体留在浏览器。首次识别会从网络下载OCR组件和语言数据。识别文字不会自动提交，只有点击核验时才发送。</p>
  </section>;
}
