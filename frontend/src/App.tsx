import * as React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { StoreProvider, useStore } from "@/lib/store";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Layout } from "@/components/Layout";
import { ShortcutsDialog } from "@/components/Shortcuts";
import { Tour } from "@/components/Tour";
import { Skeleton } from "@/components/ui/skeleton";
import Optimize from "@/pages/Optimize";

// Every page but Optimize loads on demand; index.html preloads the chunk of the page being opened.
const Compare = React.lazy(() => import("@/pages/Compare"));
const Suite = React.lazy(() => import("@/pages/Suite"));
const Results = React.lazy(() => import("@/pages/Results"));
const How = React.lazy(() => import("@/pages/How"));
const History = React.lazy(() => import("@/pages/History"));
const ImageMode = React.lazy(() => import("@/pages/ImageMode"));
const Status = React.lazy(() => import("@/pages/Status"));
const NotFound = React.lazy(() => import("@/pages/NotFound"));


function PageFallback() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading page">
      <Skeleton className="h-10 w-72" />
      <Skeleton className="h-5 w-[32rem] max-w-full" />
      <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-32" /><Skeleton className="h-32" /><Skeleton className="h-32" /></div>
    </div>
  );
}

function ThemedToaster() {
  const { theme } = useStore();
  return <Toaster theme={theme} position="bottom-right" richColors closeButton toastOptions={{ className: "font-sans" }} />;
}

export default function App() {
  return (
    <StoreProvider>
      <TooltipProvider>
        <BrowserRouter>
          <Layout>
            <React.Suspense fallback={<PageFallback />}>
              <Routes>
                <Route path="/" element={<Optimize />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="/suite" element={<Suite />} />
                <Route path="/results" element={<Results />} />
                <Route path="/how" element={<How />} />
                <Route path="/history" element={<History />} />
                <Route path="/image" element={<ImageMode />} />
                <Route path="/status" element={<Status />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </React.Suspense>
          </Layout>
          <ShortcutsDialog />
          <Tour />
          <ThemedToaster />
        </BrowserRouter>
      </TooltipProvider>
    </StoreProvider>
  );
}
