import { Html, Head, Main, NextScript } from 'next/document';

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <link rel="icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/logo-circle.jpg" />
        <meta name="theme-color" content="#f97316" />
        <meta property="og:title" content="3ioNetra — Mitra, Your Spiritual Companion" />
        <meta property="og:description" content="Find peace, guidance, and wisdom with your AI spiritual companion." />
        <meta property="og:image" content="/logo-full.png" />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:image" content="/logo-full.png" />
        <link rel="preload" as="image" href="/logo-full-dark.png" />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches))document.documentElement.classList.add('dark')}catch(e){}})()`,
          }}
        />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
