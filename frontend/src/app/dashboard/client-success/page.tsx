'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface ClientData {
  client_id: string;
  health_score: number;
  churn_probability: number;
  onboarding_rate: number;
  engagement_score: number;
  response_time: number;
  accuracy_rate: number;
  resolution_rate: number;
}

interface MetricsSummary {
  total_clients: number;
  average_health: number;
  average_churn_risk: number;
  at_risk_count: number;
  healthy_count: number;
}

export default function ClientSuccessPage() {
  const [clients, setClients] = useState<ClientData[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTab, setSelectedTab] = useState('overview');

  useEffect(() => {
    // Simulate fetching data
    const fetchData = async () => {
      setLoading(true);

      // Simulated data for all 10 clients
      const mockClients: ClientData[] = [
        { client_id: 'client_001', health_score: 85, churn_probability: 0.15, onboarding_rate: 100, engagement_score: 78, response_time: 2.1, accuracy_rate: 92, resolution_rate: 88 },
        { client_id: 'client_002', health_score: 72, churn_probability: 0.28, onboarding_rate: 85, engagement_score: 65, response_time: 3.2, accuracy_rate: 85, resolution_rate: 82 },
        { client_id: 'client_003', health_score: 91, churn_probability: 0.08, onboarding_rate: 100, engagement_score: 88, response_time: 1.8, accuracy_rate: 95, resolution_rate: 92 },
        { client_id: 'client_004', health_score: 58, churn_probability: 0.42, onboarding_rate: 60, engagement_score: 45, response_time: 4.5, accuracy_rate: 75, resolution_rate: 70 },
        { client_id: 'client_005', health_score: 79, churn_probability: 0.22, onboarding_rate: 90, engagement_score: 72, response_time: 2.8, accuracy_rate: 88, resolution_rate: 85 },
        { client_id: 'client_006', health_score: 88, churn_probability: 0.12, onboarding_rate: 95, engagement_score: 82, response_time: 2.0, accuracy_rate: 91, resolution_rate: 89 },
        { client_id: 'client_007', health_score: 45, churn_probability: 0.55, onboarding_rate: 40, engagement_score: 35, response_time: 5.8, accuracy_rate: 68, resolution_rate: 62 },
        { client_id: 'client_008', health_score: 82, churn_probability: 0.18, onboarding_rate: 88, engagement_score: 75, response_time: 2.5, accuracy_rate: 87, resolution_rate: 84 },
        { client_id: 'client_009', health_score: 76, churn_probability: 0.25, onboarding_rate: 78, engagement_score: 68, response_time: 3.0, accuracy_rate: 83, resolution_rate: 80 },
        { client_id: 'client_010', health_score: 69, churn_probability: 0.32, onboarding_rate: 70, engagement_score: 58, response_time: 3.8, accuracy_rate: 80, resolution_rate: 76 },
      ];

      const mockMetrics: MetricsSummary = {
        total_clients: 10,
        average_health: 74.5,
        average_churn_risk: 25.7,
        at_risk_count: 2,
        healthy_count: 5,
      };

      setClients(mockClients);
      setMetrics(mockMetrics);
      setLoading(false);
    };

    fetchData();
  }, []);

  const getHealthColor = (score: number) => {
    if (score >= 80) return 'bg-green-500';
    if (score >= 60) return 'bg-yellow-500';
    if (score >= 40) return 'bg-orange-500';
    return 'bg-red-500';
  };

  const getHealthBadge = (score: number) => {
    if (score >= 80) return <Badge className="bg-green-500">Excellent</Badge>;
    if (score >= 60) return <Badge className="bg-yellow-500">Good</Badge>;
    if (score >= 40) return <Badge className="bg-orange-500">Fair</Badge>;
    return <Badge className="bg-red-500">Poor</Badge>;
  };

  const getRiskBadge = (probability: number) => {
    if (probability < 0.2) return <Badge className="bg-green-500">Low Risk</Badge>;
    if (probability < 0.4) return <Badge className="bg-yellow-500">Medium Risk</Badge>;
    if (probability < 0.6) return <Badge className="bg-orange-500">High Risk</Badge>;
    return <Badge className="bg-red-500">Critical</Badge>;
  };

  const atRiskClients = clients.filter(c => c.churn_probability > 0.4 || c.health_score < 60);
  const healthyClients = clients.filter(c => c.health_score >= 80 && c.churn_probability < 0.3);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading client success data...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Client Success Dashboard</h1>
          <p className="text-gray-500">Monitor health, churn risk, and engagement for all 10 clients</p>
        </div>
        <Button>Generate Report</Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Average Health Score</CardDescription>
            <CardTitle className="text-3xl">{metrics?.average_health.toFixed(1)}%</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={`h-2 rounded-full ${getHealthColor(metrics?.average_health || 0)}`}
                style={{ width: `${metrics?.average_health}%` }}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>At-Risk Clients</CardDescription>
            <CardTitle className="text-3xl text-red-500">{metrics?.at_risk_count}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">Require immediate attention</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Healthy Clients</CardDescription>
            <CardTitle className="text-3xl text-green-500">{metrics?.healthy_count}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">Performing well</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Avg Churn Risk</CardDescription>
            <CardTitle className="text-3xl">{metrics?.average_churn_risk.toFixed(1)}%</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">Overall churn probability</p>
          </CardContent>
        </Card>
      </div>

      {/* At-Risk Alert */}
      {atRiskClients.length > 0 && (
        <Alert variant="destructive">
          <AlertTitle>Attention Required</AlertTitle>
          <AlertDescription>
            {atRiskClients.length} client(s) are at risk: {atRiskClients.map(c => c.client_id).join(', ')}
          </AlertDescription>
        </Alert>
      )}

      {/* Tabs */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="health">Health Scores</TabsTrigger>
          <TabsTrigger value="churn">Churn Risk</TabsTrigger>
          <TabsTrigger value="onboarding">Onboarding</TabsTrigger>
          <TabsTrigger value="engagement">Engagement</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>All Clients Overview</CardTitle>
              <CardDescription>Health scores and key metrics for all 10 clients</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Client</th>
                      <th className="text-left p-2">Health</th>
                      <th className="text-left p-2">Status</th>
                      <th className="text-left p-2">Risk</th>
                      <th className="text-left p-2">Accuracy</th>
                      <th className="text-left p-2">Response</th>
                    </tr>
                  </thead>
                  <tbody>
                    {clients.map((client) => (
                      <tr key={client.client_id} className="border-b hover:bg-gray-50">
                        <td className="p-2 font-medium">{client.client_id}</td>
                        <td className="p-2">
                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-gray-200 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full ${getHealthColor(client.health_score)}`}
                                style={{ width: `${client.health_score}%` }}
                              />
                            </div>
                            <span>{client.health_score}%</span>
                          </div>
                        </td>
                        <td className="p-2">{getHealthBadge(client.health_score)}</td>
                        <td className="p-2">{getRiskBadge(client.churn_probability)}</td>
                        <td className="p-2">{client.accuracy_rate}%</td>
                        <td className="p-2">{client.response_time}h</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="health" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {clients.map((client) => (
              <Card key={client.client_id}>
                <CardHeader>
                  <div className="flex justify-between items-center">
                    <CardTitle className="text-lg">{client.client_id}</CardTitle>
                    {getHealthBadge(client.health_score)}
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Health Score</span>
                        <span>{client.health_score}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full ${getHealthColor(client.health_score)}`}
                          style={{ width: `${client.health_score}%` }}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>Accuracy: {client.accuracy_rate}%</div>
                      <div>Resolution: {client.resolution_rate}%</div>
                      <div>Response: {client.response_time}h</div>
                      <div>Engagement: {client.engagement_score}%</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="churn" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>At-Risk Clients</CardTitle>
                <CardDescription>Clients with high churn probability or low health</CardDescription>
              </CardHeader>
              <CardContent>
                {atRiskClients.length === 0 ? (
                  <p className="text-green-500">No clients currently at risk!</p>
                ) : (
                  <div className="space-y-2">
                    {atRiskClients.map((client) => (
                      <div key={client.client_id} className="flex justify-between items-center p-2 bg-red-50 rounded">
                        <span className="font-medium">{client.client_id}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-red-600">{(client.churn_probability * 100).toFixed(0)}% churn risk</span>
                          {getRiskBadge(client.churn_probability)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Healthy Clients</CardTitle>
                <CardDescription>Clients with excellent health and low churn risk</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {healthyClients.map((client) => (
                    <div key={client.client_id} className="flex justify-between items-center p-2 bg-green-50 rounded">
                      <span className="font-medium">{client.client_id}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-green-600">{client.health_score}% health</span>
                        <Badge className="bg-green-500">Healthy</Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="onboarding" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Onboarding Progress</CardTitle>
              <CardDescription>Completion rates for all clients</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {clients.map((client) => (
                  <div key={client.client_id}>
                    <div className="flex justify-between text-sm mb-1">
                      <span>{client.client_id}</span>
                      <span>{client.onboarding_rate}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${client.onboarding_rate >= 80 ? 'bg-green-500' : client.onboarding_rate >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${client.onboarding_rate}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="engagement" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Engagement Scores</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {clients.map((client) => (
                    <div key={client.client_id} className="flex justify-between items-center">
                      <span>{client.client_id}</span>
                      <div className="flex items-center gap-2 w-40">
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className={`h-2 rounded-full ${client.engagement_score >= 70 ? 'bg-green-500' : client.engagement_score >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                            style={{ width: `${client.engagement_score}%` }}
                          />
                        </div>
                        <span className="text-sm w-10">{client.engagement_score}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <h4 className="font-medium mb-2">Average Response Time</h4>
                    <div className="text-2xl font-bold">
                      {(clients.reduce((sum, c) => sum + c.response_time, 0) / clients.length).toFixed(1)}h
                    </div>
                    <p className="text-sm text-gray-500">Target: &lt; 4 hours</p>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">Average Accuracy</h4>
                    <div className="text-2xl font-bold">
                      {(clients.reduce((sum, c) => sum + c.accuracy_rate, 0) / clients.length).toFixed(1)}%
                    </div>
                    <p className="text-sm text-gray-500">Target: &gt; 85%</p>
                  </div>
                  <div>
                    <h4 className="font-medium mb-2">Average Resolution Rate</h4>
                    <div className="text-2xl font-bold">
                      {(clients.reduce((sum, c) => sum + c.resolution_rate, 0) / clients.length).toFixed(1)}%
                    </div>
                    <p className="text-sm text-gray-500">Target: &gt; 80%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 flex-wrap">
            <Button variant="outline">Send Check-in Emails</Button>
            <Button variant="outline">Schedule Reviews</Button>
            <Button variant="outline">View Reports</Button>
            <Button variant="outline">Export Data</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
