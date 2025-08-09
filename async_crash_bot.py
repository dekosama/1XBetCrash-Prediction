import asyncio
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
import aiofiles
import pickle
import os
from functools import lru_cache
import logging
import gc
from concurrent.futures import ThreadPoolExecutor
import time
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from aiogram import F
import asyncio

# Configure logging for performance monitoring
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AsyncOptimizedCrashPredictor:
    def __init__(self, csv_file='1XBetCrash.csv', model_cache_dir='model_cache'):
        self.csv_file = csv_file
        self.model_cache_dir = model_cache_dir
        self.scaler = None
        self.models = {}
        self.X_scaled = None
        self.y = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Create cache directory
        os.makedirs(model_cache_dir, exist_ok=True)
    
    async def initialize(self):
        """Async initialization of models and data"""
        await self._load_and_prepare_data()
        await self._initialize_models()
    
    @lru_cache(maxsize=1)
    def _load_data_sync(self):
        """Synchronous data loading for caching"""
        logger.info("Loading data from CSV...")
        try:
            df = pd.read_csv(self.csv_file, dtype={
                'Number of players': 'int32',
                'Total bets': 'float32',
                'Multiplier': 'float32'
            })
            return df
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise
    
    async def _load_and_prepare_data(self):
        """Async data loading and preparation"""
        # Run data loading in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(self.executor, self._load_data_sync)
        
        # Extract features and target more efficiently
        feature_columns = [col for col in df.columns if col not in ['Time', 'Multiplier']]
        X = df[feature_columns].values.astype(np.float32)
        self.y = df['Multiplier'].values.astype(np.float32)
        
        # Handle scaler asynchronously
        scaler_path = os.path.join(self.model_cache_dir, 'scaler.pkl')
        if os.path.exists(scaler_path):
            logger.info("Loading cached scaler...")
            async with aiofiles.open(scaler_path, 'rb') as f:
                scaler_data = await f.read()
                self.scaler = pickle.loads(scaler_data)
            
            # Transform data in thread pool
            self.X_scaled = await loop.run_in_executor(
                self.executor, self.scaler.transform, X
            )
        else:
            logger.info("Creating and caching scaler...")
            self.scaler = StandardScaler()
            
            # Fit and transform in thread pool
            self.X_scaled = await loop.run_in_executor(
                self.executor, self.scaler.fit_transform, X
            )
            
            # Save scaler asynchronously
            scaler_data = pickle.dumps(self.scaler)
            async with aiofiles.open(scaler_path, 'wb') as f:
                await f.write(scaler_data)
        
        # Clean up
        del df, X
        gc.collect()
        
        logger.info(f"Data prepared: {self.X_scaled.shape[0]} samples, {self.X_scaled.shape[1]} features")
    
    def _get_model_cache_path(self, model_name):
        """Get cache path for a specific model"""
        return os.path.join(self.model_cache_dir, f'{model_name}.pkl')
    
    async def _load_or_train_model(self, model_class, model_name, **kwargs):
        """Async model loading or training"""
        cache_path = self._get_model_cache_path(model_name)
        
        if os.path.exists(cache_path):
            logger.info(f"Loading cached {model_name}...")
            async with aiofiles.open(cache_path, 'rb') as f:
                model_data = await f.read()
                return pickle.loads(model_data)
        else:
            logger.info(f"Training {model_name}...")
            
            # Train model in thread pool
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(
                self.executor, 
                self._train_model_sync, 
                model_class, 
                kwargs
            )
            
            # Cache the trained model asynchronously
            model_data = pickle.dumps(model)
            async with aiofiles.open(cache_path, 'wb') as f:
                await f.write(model_data)
            
            return model
    
    def _train_model_sync(self, model_class, kwargs):
        """Synchronous model training"""
        model = model_class(**kwargs)
        
        # Split data for training
        train_X, test_X, train_y, test_y = train_test_split(
            self.X_scaled, self.y, test_size=0.3, random_state=123
        )
        
        model.fit(train_X, train_y)
        
        # Clean up training data
        del train_X, test_X, train_y, test_y
        gc.collect()
        
        return model
    
    async def _initialize_models(self):
        """Async model initialization"""
        logger.info("Initializing models...")
        
        model_configs = {
            'linear_reg': (LinearRegression, {'n_jobs': -1}),
            'tree_reg': (DecisionTreeRegressor, {'random_state': 123, 'max_depth': 10}),
            'forest_reg': (RandomForestRegressor, {
                'n_estimators': 50,
                'random_state': 123,
                'max_depth': 10,
                'n_jobs': -1
            }),
            'nn_reg': (MLPRegressor, {
                'hidden_layer_sizes': (50,),
                'max_iter': 500,
                'random_state': 123,
                'early_stopping': True,
                'validation_fraction': 0.1
            })
        }
        
        # Load all models concurrently
        tasks = []
        for model_name, (model_class, kwargs) in model_configs.items():
            task = self._load_or_train_model(model_class, model_name, **kwargs)
            tasks.append((model_name, task))
        
        # Wait for all models to load
        for model_name, task in tasks:
            self.models[model_name] = await task
        
        logger.info("All models initialized successfully")
    
    async def predict_next_values(self, num_predictions=10):
        """Async prediction generation"""
        logger.info(f"Generating {num_predictions} predictions...")
        
        # Use the last available data points
        last_data_points = self.X_scaled[-num_predictions:]
        
        # Run predictions concurrently
        prediction_tasks = []
        loop = asyncio.get_event_loop()
        
        for model_name, model in self.models.items():
            task = loop.run_in_executor(
                self.executor, 
                model.predict, 
                last_data_points
            )
            prediction_tasks.append((model_name, task))
        
        # Collect results
        predictions_by_model = {}
        for model_name, task in prediction_tasks:
            try:
                predictions = await task
                predictions_by_model[model_name] = predictions.tolist()
            except Exception as e:
                logger.error(f"Error predicting with {model_name}: {e}")
                predictions_by_model[model_name] = [0.0] * num_predictions
        
        return predictions_by_model

# Global predictor instance
predictor = None

async def get_predictor():
    """Async lazy initialization of predictor"""
    global predictor
    if predictor is None:
        predictor = AsyncOptimizedCrashPredictor()
        await predictor.initialize()
    return predictor

# Create bot instance
bot = Bot(token='YOUR_TOKEN')
dp = Dispatcher()

@dp.message(Command('predict'))
async def handle_predict(message: Message):
    """Async prediction handler"""
    try:
        start_time = time.time()
        logger.info(f"Prediction request from user: {message.from_user.id}")
        
        # Send "typing" action to show bot is working
        await bot.send_chat_action(message.chat.id, 'typing')
        
        # Get predictor instance
        pred = await get_predictor()
        
        # Generate predictions
        predictions_by_model = await pred.predict_next_values(10)
        
        # Send predictions with better formatting
        tasks = []
        for model_name, predictions in predictions_by_model.items():
            model_display_name = model_name.replace('_', ' ').title()
            
            prediction_text = f"🤖 *{model_display_name}*\n"
            prediction_text += "\n".join([
                f"📊 Prediction {i+1}: {pred:.2f}x" 
                for i, pred in enumerate(predictions)
            ])
            
            # Send messages concurrently
            task = message.answer(prediction_text, parse_mode='Markdown')
            tasks.append(task)
        
        # Wait for all messages to be sent
        await asyncio.gather(*tasks)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Predictions sent in {elapsed_time:.2f}s to user: {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error handling prediction request: {e}")
        await message.answer("❌ Sorry, there was an error generating predictions. Please try again later.")

@dp.message(Command('start', 'help'))
async def handle_start(message: Message):
    """Handle start and help commands"""
    help_text = """
🎰 *1XBet Crash Prediction Bot* (Async Version)

Available commands:
/predict - Get next 10 multiplier predictions
/help - Show this help message
/stats - Show bot performance statistics

The bot uses multiple AI models to predict crash game multipliers:
• Linear Regression
• Decision Tree  
• Random Forest
• Neural Network

⚠️ *Disclaimer*: Predictions are for entertainment only. Gambling involves risk.

🚀 This async version provides faster response times and better concurrency.
    """
    await message.answer(help_text, parse_mode='Markdown')

@dp.message(Command('stats'))
async def handle_stats(message: Message):
    """Show performance statistics"""
    try:
        pred = await get_predictor()
        
        stats_text = f"""
📊 *Bot Performance Statistics*

🧠 Models loaded: {len(pred.models)}
📈 Data points: {pred.X_scaled.shape[0] if pred.X_scaled is not None else 0}
🔢 Features: {pred.X_scaled.shape[1] if pred.X_scaled is not None else 0}
💾 Cache directory: {pred.model_cache_dir}

⚡ *Performance Features*:
• Async processing for faster responses
• Model caching for instant predictions
• Concurrent model execution
• Memory-optimized data handling
        """
        
        await message.answer(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await message.answer("❌ Error retrieving statistics.")

async def main():
    """Main async function"""
    logger.info("Starting async Telegram bot...")
    
    try:
        # Initialize predictor early
        await get_predictor()
        logger.info("Predictor initialized successfully")
        
        # Start polling
        await dp.start_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot failed: {e}")
        raise