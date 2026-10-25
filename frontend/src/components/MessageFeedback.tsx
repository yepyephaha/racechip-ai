import type {ReactNode} from 'react';
import AnimatedContent from './reactbits/AnimatedContent/AnimatedContent';

export default function MessageFeedback({children}:{children:ReactNode}){
  return <AnimatedContent trigger="mount" distance={4} duration={0.18} animateOpacity={false} initialOpacity={1} style={{visibility:'visible'}}>{children}</AnimatedContent>;
}
