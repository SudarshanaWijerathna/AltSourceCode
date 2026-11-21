"use client";
// Reveals a line left to right, each character fading in a moment after the one before (the
// start-screen greeting, after Mira's mark is drawn). Every character is laid out from the start
// (only its opacity changes), so line breaks and centring never shift. Screen readers get the whole
// text at once; with reduced motion the global rule turns the fade off and the text simply shows.

export function TypedText({ text, delay = 0, msPerChar = 9 }: { text: string; delay?: number; msPerChar?: number }) {
  return (
    <span>
      <span className="typed__sr">{text}</span>
      <span aria-hidden>
        {[...text].map((ch, i) => (
          <span key={i} className="typed__ch" style={{ animationDelay: `${delay + i * msPerChar}ms` }}>{ch}</span>
        ))}
      </span>
    </span>
  );
}
