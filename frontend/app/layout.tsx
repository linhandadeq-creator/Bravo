import type { Metadata } from "next";

import { Sidebar } from "@/components/sidebar";
import { TabBar } from "@/components/tab-bar";
import { FullscreenManager } from "@/components/fullscreen-manager";
import { ThemeProvider } from "@/components/theme-provider";
import { ToastProvider } from "@/components/toast";
import { TopBar } from "@/components/top-bar";
import { I18nProvider } from "@/lib/i18n";

import "./globals.css";

export const metadata: Metadata = {
  title: "Bravo",
  description:
    "Bravo · Personalized neoantigen analysis platform — research computing & simulation.",
};

const THEME_SCRIPT = `try{var t=localStorage.getItem('bravo.theme')||'system';var d=t==='dark'||(t==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){}`;

const PREF_SCRIPT = `try{var p=JSON.parse(localStorage.getItem('bravo.ui')||'{}');var r=document.documentElement;
if(p.fontSize==='sm')r.style.fontSize='15px';else if(p.fontSize==='lg')r.style.fontSize='17.5px';
var b=(p.backdrop==='gradient'||p.backdrop==='solid'||p.backdrop==='custom')?p.backdrop:'photo';r.dataset.backdrop=b;
if(b==='custom'&&typeof p.customImage==='string'&&p.customImage)r.style.setProperty('--custom-backdrop','url("'+p.customImage+'")');
var s=(typeof p.blur==='number'?Math.max(0,Math.min(100,p.blur)):50)/50;
r.style.setProperty('--blur-1',(18*s).toFixed(1)+'px');r.style.setProperty('--blur-2',(26*s).toFixed(1)+'px');r.style.setProperty('--blur-3',(40*s).toFixed(1)+'px');
}catch(e){}`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <script dangerouslySetInnerHTML={{ __html: PREF_SCRIPT }} />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider>
          <I18nProvider>
            <ToastProvider>
            <FullscreenManager />
            <Sidebar />
            <main className="min-h-screen px-3 pb-28 lg:pb-10 lg:pl-[248px]">
              <TopBar />
              <div className="animate-page mx-auto max-w-5xl">{children}</div>
            </main>
            <TabBar />
            </ToastProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
