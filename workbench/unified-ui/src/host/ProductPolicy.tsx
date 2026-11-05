import {createContext,useContext,type ReactNode} from 'react'
const Context=createContext({upgradeRequired:false,onUpgrade:()=>{}})
export function ProductPolicyProvider({upgradeRequired,onUpgrade,children}:{upgradeRequired:boolean;onUpgrade:()=>void;children:ReactNode}){return <Context.Provider value={{upgradeRequired,onUpgrade}}>{children}</Context.Provider>}
export const useProductPolicy=()=>useContext(Context)
