#include <bits/stdc++.h>
using namespace std;

//Step 1 -- Form DSU
//Step 2 -- Implement MST

//DSU 
//1. FindSet
//2. UnionSet

//Here DSU is implemented as a class and not a function.
//In "detect_cycle.cpp", DSU was implemented as a function.

class DSU {
	int *parent;
	int *rank;
public:

	DSU(int n){
		parent = new int[n];
		rank = new int[n];

		for(int i=0;i<n;i++){
			parent[i] =-1;
			rank[i] =1;
		}
	}

	int findSet(int i){
		if(parent[i]==-1){
			return i;
		}
		return parent[i] = findSet(parent[i]);
	}

	void unionSet(int x, int y){
		int s1 = findSet(x);
		int s2 = findSet(y);

		if(s1!=s2){
			if(rank[s2]<rank[s1]){
				parent[s2] = s1;
				rank[s1]+=rank[s2];
			}
			else{
				parent[s1]=s2;
				rank[s2]+=rank[s1];
			}
		}

	}

};

//Here Graph is designed as a class containing vector of vectors containing edges and weights
// {Weight,Node1,Node2}
// eg. {1,2,3},{2,2,3},{1,1,2}


class Graph{
	int V;
	vector <vector<int> > edgelist;

public:
	Graph(int V){
		this->V = V;
	}


	void addEdge(int x, int y, int w){
		vector<int> temp;
		temp.push_back(w);
		temp.push_back(x);
		temp.push_back(y);
		edgelist.push_back(temp);
	}

	int kruskals_mst(){
		//sort the weights
		sort(edgelist.begin(),edgelist.end());

		int ans=0;
		DSU s(V);
		for(auto edges:edgelist){
			//extract the information one by one
			int w=edges[0];
			int x=edges[1];
			int y=edges[2];

			if(s.findSet(x)!=s.findSet(y)){
				s.unionSet(x,y);
				ans+=w;
				cout<<x<<"->"<<y<<endl;

			}
		}
		return ans;
	}


};

int main(){
	Graph g(4);
	//method signature
	//Node1, Node2, Weight
	g.addEdge(0,1,1);
	g.addEdge(1,3,3);
	g.addEdge(3,2,2);
	g.addEdge(2,0,2);
	g.addEdge(0,3,2);
	g.addEdge(1,2,2);
	cout<< g.kruskals_mst();


	return 0;
}















