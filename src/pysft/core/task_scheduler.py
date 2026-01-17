
# import time
# import psutil
# import asyncio
# from collections import deque
# from dataclasses import dataclass
# from typing import Optional, Any
# from enum import Enum

# import DataFetcher_Utilities as Utilities
# from DataFetcher_Utilities import fetchRequest
# import DataFetcher_Constants as Constants
# from DataFetcher_Constants import E_FetchType

# from InstanceMonitor import INSTANCE_MONITOR
# from ResourceManager import RESOURCEMANAGER

# from DF_TheMarker import fetch_tase_fast, fetch_tase_historical
# from DF_YFinance import fetch_yfinance_data

# class taskState(Enum):
#     QUEUED      = "queued"
#     RUNNING     = "running" 
#     COMPLETED   = "completed"
#     FAILED      = "failed"

# @dataclass
# class taskContainer:
#     """Container for task metadata and tracking"""
#     index: int
#     fetch_type: Constants.E_FetchType
#     task_data: Any

#     state: taskState = taskState.QUEUED

#     created_at: Optional[float] = None
#     started_at: Optional[float] = None
#     completed_at: Optional[float] = None

#     attempt_count: int = 0
    
#     # Post initialization to set created_at timestamp
#     def __post_init__(self):
#         if self.created_at is None:
#             self.created_at = time.time()
    
#     @property
#     def task_id(self) -> str:
#         """Unique task identifier"""
#         if self.created_at:
#             return f"{self.fetch_type.name}_{self.index}_{int(self.created_at)}"
#         return f"{self.fetch_type.name}_{self.index}_unknown"
    
#     @property
#     def elapsed_time(self) -> float:
#         """Time since task was created"""
#         if self.created_at:
#             return time.time() - self.created_at
#         return 0.0

# class taskScheduler:
#     """ 
#         Scheduler to manage and execute tasks with resource constraints.
#     """

#     def __init__(self, tasks: list[tuple[E_FetchType, fetchRequest | list[fetchRequest]]]):
#         self.activeTasks = 0

#         self.activeYFinance         = 0
#         self.activeTASE             = 0

#         # Task queue
#         self.queue: deque[taskContainer] = deque()  # Primary FIFO queue
        
#         # Active task tracking
#         self.running_tasks = {}  # task_id -> taskContainer
#         self.completed_tasks = {}  # task_id -> taskContainer

#         # Timer settings
#         self.timeout: float = Constants.RESOURCE_WAIT_TIMEOUT.seconds()
#         self.check_interval = 0.2 # [sec] time interval between resource checks

#         # Scheduler time tracking
#         self.scheduler_start_time = None
#         self.last_execution_time = None

#         self._initialize_tasks(tasks)

#     def _initialize_tasks(self, tasks: list[tuple[E_FetchType, fetchRequest | list[fetchRequest]]]):
#         """
#             Initialize task containers and add to main queue
#         """

#         for task_idx, (fetch_type, task_data) in enumerate(tasks):
#             task_container = taskContainer(
#                                             index=task_idx, 
#                                             fetch_type=fetch_type, 
#                                             task_data=task_data
#                                             )
#             self.queue.append(task_container)

#     async def execute(self):
#         """
#             Execute all tasks in the queues and wait until all tasks are completed
#         """

#         if not self.queue:
#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 print("No tasks to execute in the scheduler.")
#             return
        
#         # Start scheduler timer
#         self.scheduler_start_time = time.time()
#         self.last_execution_time = self.scheduler_start_time

#         while self.queue:
#             # Check global scheduler timeout
#             current_time = time.time()
#             time_since_last_execution = current_time - self.last_execution_time

#             if time_since_last_execution >= self.timeout:
#                 raise TimeoutError(f"Scheduler execution timeout reached after {self.timeout} seconds.")

#             # Get first task in queue
#             task = self.queue[0]

#             if not self.check_task_status(task.fetch_type):
#                 # No resources available, rotate task to end of queue
#                 rotated_task = self.queue.popleft()
#                 self.queue.append(rotated_task)
#                 continue

#             # Small delay in order to reduce resource contention
#             if task.fetch_type == E_FetchType.YFINANCE:
#                 await asyncio.sleep(Constants.DELAY_0p5_SEC.seconds())
#             elif task.fetch_type == E_FetchType.TASE_FAST:
#                 await asyncio.sleep(Constants.DELAY_1_SEC.seconds())
#             elif task.fetch_type == E_FetchType.TASE_HISTORICAL:
#                 await asyncio.sleep(Constants.DELAY_3_SEC.seconds())

#             if self.can_execute_task(task.fetch_type):
#                 executed_task = self.queue.popleft()

#                 if Constants.CLOUD_RUN_DEBUG_MODE:
#                     print(f"Resources available - executing {executed_task.task_id}") # task id contains fetch type, index and timestamp

#                 # Reset timer since we're executing a task
#                 self.last_execution_time = current_time

#                 # Execute task in parallel
#                 asyncio.create_task(self._execute_task(executed_task))

#                 # CRITICAL FIX: Give event loop a chance to start the task
#                 await asyncio.sleep(Constants.DELAY_1_SEC.seconds())  # Yield control to event loop immediately

#             else:
#                 self.decrease_task_count(task.fetch_type) # Decrease specific active task counter
                
#                 # No resources available
#                 rotated_task = self.queue.popleft()
#                 self.queue.append(rotated_task)

#                 # Wait before next resource check
#                 await asyncio.sleep(self.check_interval)

#         # Wait for all running tasks to complete
#         while self.running_tasks:
#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 print(f"Waiting for {len(self.running_tasks)} running tasks to complete...")
#             await asyncio.sleep(Constants.TASK_TYPICAL_TIME.seconds())

#         total_time = time.time() - self.scheduler_start_time
#         successful_tasks = len([t for t in self.completed_tasks.values() if t.state == taskState.COMPLETED])
#         failed_tasks = len([t for t in self.completed_tasks.values() if t.state == taskState.FAILED])

#         print(f"All tasks completed in {total_time:.2f}s - Successful: {successful_tasks}, Failed: {failed_tasks}")

#     @staticmethod
#     def can_execute_task(task_type: E_FetchType) -> bool:
#         """ 
#             Check if there are enough resources to execute the task. 
#         """

#         req = Constants.RESOURCE_REQ.get_requirements(task_type)

#         try:
#             total_cpu = psutil.cpu_count()
#             current_cpu_pct = psutil.cpu_percent()

#             if total_cpu:
#                 # Calculate the number of CPUs currently in use, including the one used for the main process
#                 current_cpu_in_use = (current_cpu_pct / 100) * total_cpu
#             else:
#                 print(f"Resource check failed: Unable to determine CPU count")
#                 return False # Unable to determine CPU count

#             current_memory_in_use = psutil.virtual_memory().used
#             available_memory = psutil.virtual_memory().total - current_memory_in_use
            
#             # Check if we have enough resources + buffer
#             cpu_needed = req["cpu"] # number of CPUs needed
#             memory_needed = req["memory"] # in bytes

#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 RESOURCEMANAGER.log_current_resources()

#             return (((current_cpu_in_use + cpu_needed) < (total_cpu - Constants.RESOURCE_BUFFER["cpu"])) and
#                     (((available_memory - memory_needed) > Constants.RESOURCE_BUFFER["memory"])))

#         except Exception as e:
#             print(f"Resource check failed: {e}")
#             return False

#     async def _execute_task(self, task: taskContainer):
#         """ 
#             Execute a task 
#         """

#         task.state                          = taskState.RUNNING
#         task.started_at                     = time.time()
#         self.running_tasks[task.task_id]    = task
#         self.activeTasks                    += 1

#         if Constants.CLOUD_RUN_DEBUG_MODE:
#             print(f"Executing task {task.task_id} (active: {self.activeTasks})")
        
#         try:
#             # Here we'll call the actual fetch functions
#             await self._dispatch_task_execution(task)
            
#             # Mark as completed
#             task.state = taskState.COMPLETED
#             task.completed_at = time.time()
            
#             execution_time = task.completed_at - task.started_at

#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 print(f"Task {task.task_id} completed in {execution_time:.2f}s")
            
#         except Exception as e:
#             # Mark as failed
#             task.state = taskState.FAILED
#             task.completed_at = time.time()
            
#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 print(f"Task {task.task_id} failed: {str(e)}")
        
#         finally:
#             # Cleanup
#             if task.task_id in self.running_tasks:
#                 del self.running_tasks[task.task_id]
            
#             self.completed_tasks[task.task_id] = task
#             self.activeTasks -= 1
            
#             self.decrease_task_count(task.fetch_type) # Decrease specific active task counter

#             if Constants.CLOUD_RUN_DEBUG_MODE:
#                 print(f"Task {task.task_id} finished (active: {self.activeTasks})")


#     async def _dispatch_task_execution(self, task: taskContainer):
#         """ 
#             Dispatch the actual task execution based on fetch type 
#         """
#         # Here we would call the actual data fetching functions
#         # For demonstration, we'll simulate with asyncio.sleep
        
#         if task.fetch_type == E_FetchType.YFINANCE:
#             # YFinance fetch is a sync function
#             loop = asyncio.get_event_loop()
#             await loop.run_in_executor(None, fetch_yfinance_data, task.task_data)
#         elif task.fetch_type == E_FetchType.TASE_FAST:
#             # TASE fast price fetch is a sync function
#             loop = asyncio.get_event_loop()
#             await loop.run_in_executor(None, fetch_tase_fast, task.task_data)
#         elif task.fetch_type == E_FetchType.TASE_HISTORICAL:
#             # TASE historical fetch is an async function
#             await fetch_tase_historical(task.task_data)
#         else:
#             raise ValueError(f"Unsupported fetch type: {task.fetch_type}")

#     def get_status(self) -> dict:
#         """ 
#             Get current status of the scheduler 
#         """
#         return {
#             "queue_size": len(self.queue),
#             "active_tasks": self.activeTasks,
#             "running_tasks": list(self.running_tasks.keys()),
#             "completed_tasks": len(self.completed_tasks),
#             "scheduler_uptime": time.time() - self.scheduler_start_time if self.scheduler_start_time else 0,
#             "time_since_last_execution": time.time() - self.last_execution_time if self.last_execution_time else 0
#         }
    
#     def check_task_status(self, task_type: E_FetchType) -> bool:
#         """ 
#             check if there are not too many tasks running at the same time 
#         """

#         # Check specific task type limits
#         if (task_type == E_FetchType.YFINANCE and self.activeYFinance < Constants.MAX_YFINANCE_TASKS):
#             self.activeYFinance += 1
#             return True
#         elif (task_type == E_FetchType.TASE_FAST or task_type == E_FetchType.TASE_HISTORICAL) and self.activeTASE < Constants.MAX_TASE_TASKS:
#             self.activeTASE += 1
#             return True
#         else:
#             return False
    
#     def decrease_task_count(self, task_type: E_FetchType):
#         """ 
#             Decrease the active task count for a specific fetch type 
#         """

#         # Decrement specific active task counters
#         if task_type == E_FetchType.YFINANCE:
#             self.activeYFinance -= 1
#         elif task_type == E_FetchType.TASE_FAST or task_type == E_FetchType.TASE_HISTORICAL:
#             self.activeTASE -= 1
#         else:
#             raise ValueError(f"Unsupported fetch type: {task_type}")

# # Async Caller Functions - Use Dedicated Browsers for True Parallelization
# async def fetch_yfinance_data_async(requests: list[fetchRequest]) -> list[fetchRequest]:
#     """
#     Async caller for YFinance data fetching.
#     Limited by semaphore to control concurrent API requests.
#     """

#     # async with request_semaphore:  # Limit concurrent API requests
#     start_time = time.time()
#     while time.time() - start_time < INSTANCE_MONITOR.waitTimeout:
#         decision = INSTANCE_MONITOR.can_start_task("YFinance")
#         if decision["can_start"]:
#             # Can start task, acquiring API slot

#             task_name = f"YFinance-{len(requests)}"

#             INSTANCE_MONITOR.start_task(task_name)

#             try:
#                 async with RESOURCEMANAGER.acquire_api_slot("YFinance"):  # Limit concurrent API requests
#                     loop = asyncio.get_event_loop()
#                     # Run the sync YFinance function in executor (no browser needed)
#                     await loop.run_in_executor(None, fetch_yfinance_data, requests)

#             except Exception as e:
#                 for request in requests:
#                     request.fetched_price = None
#                     request.success = False
#                     request.message = f"Error in async YFinance fetch: {str(e)}"
            
#             finally:
#                 # complete task
#                 INSTANCE_MONITOR.complete_task(task_name) 
            
#             return requests
#         else:
#             await asyncio.sleep(decision["wait_time"])

#     for request in requests:
#         request.success = False
#         request.message = "Timeout reached while waiting for resources to fetch YFinance data"

#     return requests

# # async def fetch_tase_fast_price_async(request: fetchRequest, request_semaphore: asyncio.Semaphore) -> fetchRequest:
# async def fetch_tase_fast_price_async(request: fetchRequest) -> fetchRequest:
#     """
#         Async caller for TASE current price fetching using fast requests method.
#         Limited by semaphore to control concurrent requests.
#     """

#     start_time = time.time()
#     while time.time() - start_time < INSTANCE_MONITOR.waitTimeout:
#         decision = INSTANCE_MONITOR.can_start_task("TASE-Fast")
#         if decision["can_start"]:
#             # Can start task, acquiring API slot

#             task_name = f"TASE-Fast-{request.indicator}"

#             INSTANCE_MONITOR.start_task(task_name)

#             try:
#                 async with RESOURCEMANAGER.acquire_api_slot(task_name):  # Limit concurrent API requests
#                     loop = asyncio.get_event_loop()
#                     # Run the sync current price function in executor (no browser needed)
#                     await loop.run_in_executor(None, fetch_tase_fast, request)

#             except Exception as e:
#                 request.success = False
#                 request.message = f"Error in async TASE current price fetch: {str(e)}"
            
#             finally:
#                 # complete task
#                 INSTANCE_MONITOR.complete_task(task_name) 
            
#             return request
#         else:
#             await asyncio.sleep(decision["wait_time"])
    
#     request.success = False
#     request.message = "Timeout reached while waiting for resources to fetch TASE fast price"
#     return request

# async def fetch_tase_historical_data_async(request: fetchRequest) -> fetchRequest:
#     """
#         Async caller for TASE historical data with DEDICATED browser instance.
#         Limited by semaphore to control concurrent browser instances.
#     """

#     start_time = time.time()
#     while time.time() - start_time < INSTANCE_MONITOR.waitTimeout:
#         decision = INSTANCE_MONITOR.can_start_task("TASE-Historical")
#         if decision["can_start"]:
#             # Can start task, acquiring browser and memory slots

#             task_name = f"TASE-Historical-{request.indicator}"

#             INSTANCE_MONITOR.start_task(task_name)

#             try:
#                 async with RESOURCEMANAGER.acquire_browser_slot(task_name):  # Limit concurrent browser instances
#                     async with RESOURCEMANAGER.acquire_memory_slot(task_name):
#                         # Run the sync function in executor for true parallelism
#                         await fetch_tase_historical(request)

#             except Exception as e:
#                 request.success = False
#                 request.message = f"Error in async TASE historical fetch: {str(e)}"
            
#             finally:
#                 # complete task
#                 INSTANCE_MONITOR.complete_task(task_name) 
            
#             return request
#         else:
#             await asyncio.sleep(decision["wait_time"])
        
#     request.success = False
#     request.message = "Timeout reached while waiting for resources to fetch TASE historical data"
#     return request