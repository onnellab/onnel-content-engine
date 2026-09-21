import React, {useMemo} from 'react';
import {layoutText} from './text-layout.mjs';

export const fontFamily = '"Noto Sans KR", "Noto Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

export const CaptionText: React.FC<{text: string; width: number; size: number; weight: number}> = ({text, width, size, weight}) => {
  const layout = useMemo(() => {
    const context = document.createElement('canvas').getContext('2d');
    if (!context) throw new Error('Text measurement unavailable');
    return layoutText(text, width, size, (line, px) => {
      context.font = `${weight} ${px}px ${fontFamily}`;
      return context.measureText(line).width;
    });
  }, [text, width, size, weight]);
  return <span style={{fontSize: layout.size, fontWeight: weight, whiteSpace: 'pre', lineHeight: 1.3}}>{layout.text}</span>;
};
