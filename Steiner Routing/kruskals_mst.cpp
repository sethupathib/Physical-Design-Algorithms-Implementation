#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;


//DSU Class

class DSU {

int *parent;
int *rank;

public:
	DSU(int n){
	  parent = new int[n];
	 rank = new int[n];

	 for(int i=0;i<n;i++){
	 	parent[i] = -1;
	 	rank[i] = 1;
	 }
	} 

	//Find Function 
	int find(int i){

		//base case

		if(parent[i]==-1){
			return i;
		}
		//path compression optimisation
		return parent[i] = find(parent[i]);


	}

	//Unite Function 
	void unite(int x, int y){
		int s1 = find(x);
		int s2 = find(y);

		//the code below unites the two components without union by rank compression

		// if(s1!= s2){
		// 	parent[s1] = s2;  
		if(s1!=s2){
		if(rank[s1]<rank[s2]){
			parent[s1] = s2;
			rank[s2]+= rank[s1];
		}
		else{
			parent[s2] = s1;
		rank[s1]+= rank[s2];

		}
		}
	}
	

};


class Graph{

int V;
vector<vector <int> > edgelist;

public:
Graph(int V){
	this->V = V;

}

void addEdge(int x, int y, int w){
	vector<int> tmp;
	tmp.push_back(w);
	tmp.push_back(x);
	tmp.push_back(y);
	
	edgelist.push_back(tmp);
}

	int kruskals_mst(){

		//main logic -- easy
		//sort all the edges based on weight
		sort(edgelist.begin(), edgelist.end());

		int ans =0;
		DSU s(V);

		
		for(auto edge: edgelist){
			int w = edge[0];
			int x = edge[1];
			int y = edge[2];

			//take that edge in MST if it doesn't form a cycle

			if(s.find(x)!= s.find(y)){
				s.unite(x,y);
				ans+=w; 
				cout<<x<<" ->"<<y<<endl;
			}
		}
		return ans;
	}

};

int main(){

	Graph g(4);
	g.addEdge(0,1,1);
	g.addEdge(1,3,3);
	g.addEdge(3,2,2);
	g.addEdge(2,0,2);
	g.addEdge(0,3,2);
	g.addEdge(1,2,2);
	cout<< g.kruskals_mst();



	return 0;
}



 


