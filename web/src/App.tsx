import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { OverviewPage } from "./pages/OverviewPage";
import { MarketPage } from "./pages/MarketPage";
import { MethodologyPage } from "./pages/MethodologyPage";

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="methodology" element={<MethodologyPage />} />
        <Route path=":id" element={<MarketPage />} />
      </Route>
    </Routes>
  );
}
