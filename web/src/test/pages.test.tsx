import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi as vitest } from "vitest";
import overview from "../../../tests/fixtures/site/overview.json";
import gold from "../../../tests/fixtures/site/gold.json";
import { OverviewPage } from "../pages/OverviewPage";
import { MarketPage } from "../pages/MarketPage";
import { MethodologyPage } from "../pages/MethodologyPage";

const files: Record<string, unknown> = { overview, gold };
vitest.mock("../lib/loader", () => ({
  loadFile: (name: string) => Promise.resolve(files[name]),
  loadManifest: () => Promise.resolve(null),
}));

describe("pages render against fixtures", () => {
  it("overview shows composites, market cards and disclaimer", async () => {
    render(
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Điều kiện tài chính")).toBeInTheDocument();
    expect(screen.getByText("Kinh tế toàn cầu")).toBeInTheDocument();
    expect(screen.getAllByText(/Độ tin cậy/).length).toBeGreaterThan(0);
    expect(screen.getByText("Không phải lời khuyên đầu tư")).toBeInTheDocument();
  });

  it("market page shows both horizons, confidence, n_eff and baseline skill", async () => {
    render(
      <MemoryRouter initialEntries={["/gold"]}>
        <Routes>
          <Route path=":id" element={<MarketPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Vàng" })).toBeInTheDocument();
    expect(screen.getByLabelText("Ngắn hạn")).toBeInTheDocument();
    expect(screen.getByLabelText("Trung hạn")).toBeInTheDocument();
    expect(screen.getAllByText(/n_eff/).length).toBe(2);
    expect(screen.getAllByText("Chưa vượt đường cơ sở").length).toBeGreaterThan(0);
  });

  it("methodology page renders", () => {
    render(<MethodologyPage />);
    expect(screen.getByRole("heading", { name: "Phương pháp" })).toBeInTheDocument();
  });
});
