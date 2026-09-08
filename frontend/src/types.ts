export type Prediction = {
  abnormality: string;
  probability: number;
  confidenceLevel: string;
};

export type Study = {
  studyId: string;
  createdAt: string;
  status: string;
  imageCount: number;
  analysisStatus: string;
  priority: string;
  overallRisk: number;
  files?: Array<{ filename: string; path: string }>;
};

export type UploadResponse = {
  studyId: string;
  imageCount: number;
  status: string;
};

export type TopFinding = {
  abnormality: string;
  probability: number;
  confidence: string;
};

export type AnalysisResponse = {
  studyId: string;
  analysisStatus: string;
  priority: string;
  overallRisk: number;
  predictions: Prediction[];
  topFindings: TopFinding[];
  report: Report;
  inferenceMode: string;
};

export type Report = {
  studyId: string;
  findings: string;
  impression: string;
  recommendation: string;
  generatedAt: string;
  reviewStatus: string;
};

export type HealthStatus = {
  status: string;
  service: string;
  database: { status: string; database: string };
  modelMode: string;
  timestamp: string;
};

export type ModelStatus = {
  modelMode: string;
  modelVersion: string;
  status: string;
  realModelAvailable: boolean;
  provider: string;
};
